"""Exercise the frontend gateway, simulated ledger, and AI over local HTTP."""

from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from run_demo import ASSESSMENT, USER, demo_stack


def checked(client, method, path, body=None, *, expected=200):
    code, data = client.request(method, path, body)
    if code != expected:
        raise AssertionError(f"{method} {path} returned HTTP {code}, expected {expected}: {data}")
    return data


def check_html(url):
    with urlopen(url, timeout=5) as page:
        assert b'<body data-integrated="true">' in page.read()
    with urlopen(url + "/integration.js", timeout=5) as script:
        assert b"/api/assistant/chat" in script.read()
    try:
        urlopen(url + "/.env.example", timeout=5)
    except HTTPError as error:
        assert error.code == 404
    else:
        raise AssertionError("the demo served a non-public file")
    try:
        urlopen(Request(url + "/api/profile", headers={"Origin": "http://example.test"}), timeout=5)
    except HTTPError as error:
        assert error.code == 403
    else:
        raise AssertionError("the demo accepted a foreign origin")


def questionnaire(ui, middle, ai):
    beginner = {**ASSESSMENT, "assessment": {**ASSESSMENT["assessment"],
                "dimensions": {**ASSESSMENT["assessment"]["dimensions"], "KE": 30}}}
    checked(middle, "PUT", f"/api/accounts/{USER}/assessment", beginner)
    education = checked(ui, "POST", "/api/assistant/chat", {"message": "什么是滑点？"})
    assert education["mode"] == "education" and education["reply"]

    profile = {**ASSESSMENT, "assessment": {**ASSESSMENT["assessment"], "rai": 66, "risk_level": "C4", "product_cap": "R4"}}
    result = checked(ui, "PUT", "/api/profile", profile)
    actual = checked(ui, "GET", "/api/profile")["assessment"]
    authoritative = checked(middle, "GET", f"/api/accounts/{USER}/assessment")["assessment"]
    assert actual == {"allocation_range": None, **authoritative}
    assert actual == result["assessment"] == checked(ai, "GET", f"/v1/profiles/{USER}")["assessment"]
    assert actual["risk_level"] == "C4" and actual["product_cap"] == "R4"
    assert checked(ui, "PUT", "/api/profile", {"assessment": {}}, expected=400)["error"]["code"] == "invalid_assessment"


def trade(ui):
    buy = {"symbol": "BTC/USDT", "side": "buy", "quantity": "0.01", "order_type": "market"}
    before = checked(ui, "GET", "/api/account/summary")
    checked(ui, "POST", "/api/orders", buy, expected=400)
    declined = checked(ui, "POST", "/api/orders/preview", {**buy, "quantity": "0.5"}, expected=409)
    assert declined["error"]["code"] == "insufficient_balance"
    estimate = checked(ui, "POST", "/api/orders/preview", buy)
    assert estimate["source"] == "demo:HashKey" and estimate["reference_price"] == "68001"
    assert checked(ui, "GET", "/api/orders")["orders"] == []
    assert checked(ui, "GET", "/api/account/summary")["portfolio"]["balances"] == before["portfolio"]["balances"]
    ticket = {"preview_id": estimate["preview_id"]}
    checked(ui, "POST", "/api/orders", {**ticket, "quantity": "0.02"}, expected=400)
    filled = checked(ui, "POST", "/api/orders", ticket)
    assert filled["status"] == "filled"
    assert filled == checked(ui, "POST", "/api/orders", ticket)
    assert checked(ui, "GET", f"/api/orders/{filled['order_id']}")["status"] == "filled"
    assert checked(ui, "GET", "/api/account/transactions?limit=20")["total"] == 1
    sell = {**buy, "side": "sell", "order_type": "limit", "limit_price": "70000", "quantity": "0.005"}
    estimate = checked(ui, "POST", "/api/orders/preview", sell)
    pending = checked(ui, "POST", "/api/orders", {"preview_id": estimate["preview_id"]})
    assert pending["status"] == "open"
    return pending["order_id"]


def main():
    with demo_stack(ui_port=0) as (ui, middle, ai, reader, url):
        check_html(url)
        health = checked(ui, "GET", "/api/health")
        assert set(health["services"]) == {"middle_office", "ai"}
        assert not health["services"]["ai"]["remote_model_configured"]
        print("PASS frontend assets, loopback origin, and both backend health checks")

        questionnaire(ui, middle, ai)
        print("PASS questionnaire scores and product cap persist in middle office and AI")

        query = urlencode({"symbol": "BTC/USDT", "quantity": "0.01", "side": "buy"})
        venue_report = checked(ui, "GET", "/api/market/venues?" + query)
        assert venue_report["status"] == "ok" and len(venue_report["venues"]) == 2
        assert {row["source"] for row in venue_report["venues"]} == {"demo:HashKey", "demo:OSL"}
        assert all(row["quote_currency"] == "USDT" and row["price"] and row["as_of"] for row in venue_report["venues"])
        print("PASS frontend receives both venues with currency, price, and timestamp")

        order_id = trade(ui)
        print("PASS read-only preview, insufficient funds, simulated fill, duplicate submit, pending order")

        chat = checked(ui, "POST", "/api/assistant/chat", {
            "user_id": "untrusted_browser_id", "message": "查一下比特币报价、我的持仓和挂单",
            "include_account": True, "market_queries": ["BTC/USDT"],
        })
        assert chat["reply"] and "模拟报价" in chat["reply"]
        assert chat["generation"] == "template" and chat["mode"] == "advisory" and chat["product_cap"] == "R4"
        assert chat["market"][0]["status"] == "exact" and chat["market"][0]["matches"][0]["freshness"] == "fresh"
        assert chat["account"]["state"] == "ok"
        assert {"symbol": "BTC", "quantity": "0.11"} in chat["account"]["positions"]
        assert chat["account"]["open_orders"][0]["side"] == "sell"
        assert chat["account"]["open_orders"][0]["quantity"] == "0.005"
        assert "BTC/USDT 卖出 0.005" in chat["reply"]
        print("PASS chat uses confirmed profile, exact quote, holdings, and open order")

        risk = checked(ui, "GET", "/api/risk?quote_currency=USDT")
        ledger = checked(ui, "GET", "/api/account/summary")
        assert risk["state"] == "ok" and risk["summary"]["open_order_count"] == 1
        assert ledger["snapshot_id"] and ledger["portfolio"]["state"] == "ok"
        assert ledger["account"]["open_orders"][0]["order_id"] == order_id
        cancelled = checked(ui, "POST", f"/api/orders/{order_id}/cancel", {})
        assert cancelled["status"] == "cancelled"
        assert checked(ui, "GET", "/api/account/summary")["account"]["open_orders"] == []
        checked(reader, "POST", f"/api/accounts/{USER}/orders", {}, expected=403)
        checked(reader, "POST", f"/api/accounts/{USER}/orders/preview", {}, expected=403)
        print("PASS account snapshot, AI risk, order cancellation, and read-only AI permissions")


if __name__ == "__main__":
    main()
