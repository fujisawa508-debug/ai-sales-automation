import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from mcp.server import MCPServer

mcp = MCPServer("finance-tools")


@mcp.tool()
def calculate_total(numbers: list[float]) -> float:
    """Calculate the total of a list of numbers."""
    return sum(numbers)


@mcp.tool()
def calculate_average(numbers: list[float]) -> float:
    """Calculate the average of a list of numbers."""
    if not numbers:
        raise ValueError("numbers must not be empty")

    return sum(numbers) / len(numbers)


@mcp.tool()
def get_exchange_rate(base: str, quote: str) -> dict:
    """Fetch the exchange rate from base currency to quote currency via the Frankfurter API."""
    if not base or not quote:
        raise ValueError("base and quote must not be empty")

    base = base.upper()
    quote = quote.upper()

    if base == quote:
        return {
            "date": date.today().isoformat(),
            "base": base,
            "quote": quote,
            "rate": 1.0,
        }

    url = f"https://api.frankfurter.dev/v2/rate/{base}/{quote}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "finance-tools-mcp/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"為替レートの取得に失敗しました(HTTPステータス: {e.code})"
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(
            f"為替レートの取得に失敗しました(ネットワークエラー: {e.reason})"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"為替レートのレスポンス解析に失敗しました: {e}"
        ) from e

    return {
        "date": data["date"],
        "base": data["base"],
        "quote": quote,
        "rate": data["rate"],
    }


@mcp.tool()
def get_stock_info(symbol: str) -> dict:
    """Fetch the latest stock quote for a symbol via the Alpha Vantage API."""
    if not symbol:
        raise ValueError("symbol must not be empty")

    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError(
            "環境変数 ALPHA_VANTAGE_API_KEY が設定されていません"
        )

    symbol = symbol.upper()
    params = urllib.parse.urlencode(
        {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": api_key,
        }
    )
    url = f"https://www.alphavantage.co/query?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "finance-tools-mcp/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"株価情報の取得に失敗しました(HTTPステータス: {e.code})"
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(
            f"株価情報の取得に失敗しました(ネットワークエラー: {e.reason})"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"株価情報のレスポンス解析に失敗しました: {e}"
        ) from e

    quote = data.get("Global Quote")
    if not quote:
        raise ValueError(f"銘柄コード '{symbol}' の株価情報が見つかりませんでした")

    return {
        "symbol": quote.get("01. symbol", symbol),
        "latest_price": float(quote["05. price"]),
        "open": float(quote["02. open"]),
        "high": float(quote["03. high"]),
        "low": float(quote["04. low"]),
        "volume": int(quote["06. volume"]),
        "latest_trading_day": quote["07. latest trading day"],
    }


def _fetch_japanese_stock_info(code: str) -> dict:
    """J-Quants API (V2) から日本株の直近取得可能な日足株価を取得する内部ヘルパー。"""
    if not code:
        raise ValueError("code must not be empty")

    api_key = os.environ.get("JQUANTS_API_KEY")
    if not api_key:
        raise ValueError(
            "環境変数 JQUANTS_API_KEY が設定されていません"
        )

    params = urllib.parse.urlencode({"code": code})
    url = f"https://api.jquants.com/v2/equities/bars/daily?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "finance-tools-mcp/1.0",
            "Accept": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"日本株の株価情報の取得に失敗しました(HTTPステータス: {e.code})"
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(
            f"日本株の株価情報の取得に失敗しました(ネットワークエラー: {e.reason})"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"日本株の株価情報のレスポンス解析に失敗しました: {e}"
        ) from e

    quotes = data.get("data") or []
    if not quotes:
        raise ValueError(f"銘柄コード '{code}' の日足株価が見つかりませんでした")

    latest = max(quotes, key=lambda q: q["Date"])

    return {
        "code": latest.get("Code", code),
        "date": latest["Date"],
        "open": latest["O"],
        "high": latest["H"],
        "low": latest["L"],
        "close": latest["C"],
        "volume": latest["Vo"],
    }


@mcp.tool()
def get_japanese_stock_info(code: str) -> dict:
    """J-Quants API (V2) を使って、日本株の銘柄コードから直近取得可能な日足株価を取得する。"""
    return _fetch_japanese_stock_info(code)


def _parse_optional_float(value):
    """空文字や None を許容しつつ、財務項目の文字列を float に変換する。"""
    if value in (None, ""):
        return None
    return float(value)


def _fetch_raw_financial_statements(code: str, error_label: str = "財務情報") -> list[dict]:
    """J-Quants API (V2) の fins/summary から、指定銘柄の財務諸表データ(生のレコード一覧)を取得する内部ヘルパー。

    同一銘柄について複数の分析(単年度の指標・年次推移)を行う場合、呼び出し側が
    この関数の戻り値を使い回すことで、同一APIへの重複呼び出しを避けられる
    (generate_investment_summary から利用)。
    error_label は、取得・解析エラー時のメッセージ文言を呼び出し元(単年度指標/年次推移)
    に合わせて出し分けるためのもの。
    """
    if not code:
        raise ValueError("code must not be empty")

    api_key = os.environ.get("JQUANTS_API_KEY")
    if not api_key:
        raise ValueError(
            "環境変数 JQUANTS_API_KEY が設定されていません"
        )

    params = urllib.parse.urlencode({"code": code})
    url = f"https://api.jquants.com/v2/fins/summary?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "finance-tools-mcp/1.0",
            "Accept": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"{error_label}の取得に失敗しました(HTTPステータス: {e.code})"
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(
            f"{error_label}の取得に失敗しました(ネットワークエラー: {e.reason})"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{error_label}のレスポンス解析に失敗しました: {e}"
        ) from e

    statements = data.get("data") or []
    if not statements:
        raise ValueError(f"銘柄コード '{code}' の財務情報が見つかりませんでした")

    return statements


def _fetch_financial_metrics(code: str, statements: list[dict] | None = None) -> dict:
    """J-Quants API (V2) から日本株の直近の財務情報(1件)を取得する内部ヘルパー。

    statements を渡した場合は API 呼び出しを行わず、そのデータから直近1件を抽出する
    (同一銘柄で複数の分析を行う際の重複API呼び出し回避用)。
    """
    if not code:
        raise ValueError("code must not be empty")

    if statements is None:
        statements = _fetch_raw_financial_statements(code, error_label="財務情報")

    latest = max(statements, key=lambda s: s["DiscDate"])

    return {
        "code": latest.get("Code", code),
        "date": latest["DiscDate"],
        "revenue": _parse_optional_float(latest.get("Sales")),
        "operating_profit": _parse_optional_float(latest.get("OP")),
        "profit": _parse_optional_float(latest.get("NP")),
        "eps": _parse_optional_float(latest.get("EPS")),
        "equity": _parse_optional_float(latest.get("Eq")),
        "roe": _parse_optional_float(latest.get("ROE")),
        "dividend": _parse_optional_float(latest.get("DivAnn")),
        "bps": _parse_optional_float(latest.get("BPS")),
        "shareholders_equity": _parse_optional_float(latest.get("ShEq")),
        "shares_outstanding_fy": _parse_optional_float(latest.get("ShOutFY")),
        "treasury_shares_fy": _parse_optional_float(latest.get("TrShFY")),
    }


@mcp.tool()
def get_financial_metrics(code: str) -> dict:
    """J-Quants API (V2) を使って、日本株の銘柄コードから直近の財務情報(1件)を取得する。"""
    return _fetch_financial_metrics(code)


def _is_annual_disclosure(statement: dict) -> bool:
    """CurPerType(当会計期間の種類)が "FY"(本決算)かどうかを判定する。"""
    return statement.get("CurPerType") == "FY"


def _is_actual_financial_statement(statement: dict) -> bool:
    """DocType(開示書類種別)が実績を伴う財務諸表の開示かどうかを判定する。

    配当予想の修正や業績予想の修正のみの開示は、DocType に "FinancialStatements" を
    含まない(例: DividendForecastRevision, EarnForecastRevision)ため、これらを除外する。
    """
    doc_type = statement.get("DocType")
    return isinstance(doc_type, str) and "FinancialStatements" in doc_type


def _select_annual_financial_statements(statements: list[dict], years: int) -> list[dict]:
    """本決算(CurPerType == "FY")のレコードを事業年度ごとに1件へ絞り込み、直近 years 年分を返す。

    事業年度の識別には CurFYEn(事業年度終了日)を使う。DiscDate(開示日)は決算発表が
    翌年にずれ込むケースがあり年度の判定を誤るため、グルーピングキーには使わない。

    同一事業年度に複数件ある場合の優先順位:
      1. DocType が "FY" で始まり、かつ "FinancialStatements" を含む実績本決算を優先する
         (数値を伴わない業績予想・配当予想の修正のみの開示を除外する)。
      2. その中で DocType に "_Consolidated_" を含むもの(連結決算)を
         "_NonConsolidated_"(非連結決算)より優先する(投資判断で通常参照されるのは
         連結決算のため。同一年度に連結・非連結の両方が開示されるケースがある)。
      3. さらにその中で DiscDate が最も新しいもの(訂正後の最新版)を採用する。
    各段階で候補が0件になった場合は、直前の段階の候補集合にフォールバックする
    (絞り込みすぎてデータが欠落するのを避けるため)。
    """
    annual = [s for s in statements if _is_annual_disclosure(s)]

    groups: dict[str, list[dict]] = {}
    for statement in annual:
        fiscal_year_end = statement.get("CurFYEn") or statement.get("DiscDate")
        if not fiscal_year_end:
            continue
        groups.setdefault(fiscal_year_end, []).append(statement)

    def _is_consolidated(statement: dict) -> bool:
        doc_type = statement.get("DocType")
        return isinstance(doc_type, str) and "_Consolidated_" in doc_type

    selected = []
    for fiscal_year_end, candidates in groups.items():
        actual_statements = [
            c
            for c in candidates
            if _is_actual_financial_statement(c) and str(c.get("DocType", "")).startswith("FY")
        ]
        pool = actual_statements or candidates

        consolidated = [c for c in pool if _is_consolidated(c)]
        pool = consolidated or pool

        best = max(pool, key=lambda c: c["DiscDate"])
        selected.append((fiscal_year_end, best))

    selected.sort(key=lambda pair: pair[0], reverse=True)

    return [statement for _, statement in selected[:years]]


def _fetch_financial_history(
    code: str, years: int = 5, statements: list[dict] | None = None
) -> list[dict]:
    """J-Quants API (V2) から日本株の年次(本決算)の財務推移を、直近 years 年分取得する内部ヘルパー。

    statements を渡した場合は API 呼び出しを行わず、そのデータから年次分を抽出する
    (同一銘柄で複数の分析を行う際の重複API呼び出し回避用)。
    """
    if not code:
        raise ValueError("code must not be empty")
    if not 1 <= years <= 10:
        raise ValueError("years は 1〜10 の範囲で指定してください")

    if statements is None:
        statements = _fetch_raw_financial_statements(code, error_label="財務推移情報")

    annual_statements = _select_annual_financial_statements(statements, years)
    if not annual_statements:
        raise ValueError(f"銘柄コード '{code}' の本決算(年次)データが見つかりませんでした")

    return [
        {
            "disclosure_date": statement["DiscDate"],
            "fiscal_year_end": statement.get("CurFYEn"),
            "revenue": _parse_optional_float(statement.get("Sales")),
            "operating_profit": _parse_optional_float(statement.get("OP")),
            "profit": _parse_optional_float(statement.get("NP")),
            "eps": _parse_optional_float(statement.get("EPS")),
            "roe": _parse_optional_float(statement.get("ROE")),
            "dividend": _parse_optional_float(statement.get("DivAnn")),
        }
        for statement in annual_statements
    ]


@mcp.tool()
def get_financial_history(code: str, years: int = 5) -> list[dict]:
    """J-Quants API (V2) を使って、日本株の銘柄コードから年次(本決算)の財務推移を直近 years 年分取得する。"""
    return _fetch_financial_history(code, years)


_TREND_GROWTH_THRESHOLD_PERCENT = 1.0
_TREND_POINT_THRESHOLD = 0.5


def _calculate_growth_percent(current, previous):
    """(当年 - 前年) / 前年 * 100 の成長率を計算する。前年が0またはNoneならNoneを返す。"""
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 2)


def _calculate_diff(current, previous):
    """current - previous の単純差分を計算する。どちらかがNoneならNoneを返す。"""
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def _calculate_roe_change_percent_points(current_roe, previous_roe):
    """ROE(0.101のような小数)の前年差を percentage points で計算する。どちらかがNoneならNoneを返す。"""
    if current_roe is None or previous_roe is None:
        return None
    return round((current_roe - previous_roe) * 100, 2)


def _classify_trend(values: list, threshold: float) -> str:
    """数値系列(Noneは除外)の平均を閾値と比較し、増加傾向/減少傾向/横ばいを判定する。

    有効な値が1つもない場合は判定不可とする。
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return "判定不可"

    average = sum(valid) / len(valid)
    if average > threshold:
        return "増加傾向"
    if average < -threshold:
        return "減少傾向"
    return "横ばい"


def _analyze_financial_trend(
    code: str, years: int = 5, history: list[dict] | None = None
) -> dict:
    """_fetch_financial_history の結果を使って、年度間の財務トレンドを分析する内部ヘルパー。

    fiscal_year_end を年度として使用する。disclosure_date は内部の history データには
    残るが、分析結果の出力には含めない。取得できた年度数が2年未満の場合はトレンド
    分析不可として扱う。買い・売り等の投資判断は行わない。
    history を渡した場合は _fetch_financial_history を呼び直さない
    (同一銘柄で複数の分析を行う際の重複API呼び出し回避用)。
    """
    if history is None:
        history = _fetch_financial_history(code, years)
    years_available = len(history)

    if years_available < 2:
        return {
            "code": code,
            "years_available": years_available,
            "trend_analysis_available": False,
            "comparison_type": "分析不可",
            "periods": [],
            "revenue_trend": "判定不可",
            "profit_trend": "判定不可",
            "profitability_trend": "判定不可",
            "roe_trend": "判定不可",
            "dividend_trend": "判定不可",
        }

    # fiscal_year_end 昇順(古い年度→新しい年度)に並べ替えて前年比較を行う。
    ascending = sorted(
        history,
        key=lambda h: h.get("fiscal_year_end") or h.get("disclosure_date") or "",
    )

    yearly_margins = [
        _safe_operating_margin_percent(h.get("operating_profit"), h.get("revenue"))
        for h in ascending
    ]

    periods = []
    for i in range(1, len(ascending)):
        previous = ascending[i - 1]
        current = ascending[i]
        periods.append(
            {
                "fiscal_year_end": current.get("fiscal_year_end"),
                "revenue_growth_percent": _calculate_growth_percent(
                    current.get("revenue"), previous.get("revenue")
                ),
                "operating_profit_growth_percent": _calculate_growth_percent(
                    current.get("operating_profit"), previous.get("operating_profit")
                ),
                "profit_growth_percent": _calculate_growth_percent(
                    current.get("profit"), previous.get("profit")
                ),
                "eps_growth_percent": _calculate_growth_percent(
                    current.get("eps"), previous.get("eps")
                ),
                "roe_change_percent_points": _calculate_roe_change_percent_points(
                    current.get("roe"), previous.get("roe")
                ),
                "dividend_change_yen": _calculate_diff(
                    current.get("dividend"), previous.get("dividend")
                ),
                "dividend_growth_percent": _calculate_growth_percent(
                    current.get("dividend"), previous.get("dividend")
                ),
                "operating_margin_percent": yearly_margins[i],
            }
        )

    margin_diffs = [
        _calculate_diff(yearly_margins[i], yearly_margins[i - 1])
        for i in range(1, len(yearly_margins))
    ]

    comparison_type = "前年比較" if years_available == 2 else "複数年トレンド"

    return {
        "code": code,
        "years_available": years_available,
        "trend_analysis_available": True,
        "comparison_type": comparison_type,
        "periods": periods,
        "revenue_trend": _classify_trend(
            [p["revenue_growth_percent"] for p in periods], _TREND_GROWTH_THRESHOLD_PERCENT
        ),
        "profit_trend": _classify_trend(
            [p["profit_growth_percent"] for p in periods], _TREND_GROWTH_THRESHOLD_PERCENT
        ),
        "profitability_trend": _classify_trend(margin_diffs, _TREND_POINT_THRESHOLD),
        "roe_trend": _classify_trend(
            [p["roe_change_percent_points"] for p in periods], _TREND_POINT_THRESHOLD
        ),
        "dividend_trend": _classify_trend(
            [p["dividend_growth_percent"] for p in periods], _TREND_GROWTH_THRESHOLD_PERCENT
        ),
    }


@mcp.tool()
def analyze_financial_trend(code: str, years: int = 5) -> dict:
    """日本株の銘柄コードから年次財務推移を取得し、増収・増益・収益性・ROE・配当のトレンドを整理する。

    fiscal_year_end を年度として使用し、disclosure_date は結果に含めない。
    最終的な投資判断(買い/売り)は行わない。
    """
    return _analyze_financial_trend(code, years)


@mcp.tool()
def calculate_valuation_metrics(price: float, eps: float, dividend: float) -> dict:
    """株価・EPS・配当から PER と配当利回りを計算する。"""
    if price <= 0:
        raise ValueError("price は 0 より大きい値である必要があります")
    if eps <= 0:
        raise ValueError("eps は 0 より大きい値である必要があります")
    if dividend < 0:
        raise ValueError("dividend は負の値にできません")

    per = price / eps
    dividend_yield = dividend / price * 100

    return {
        "price": round(price, 2),
        "eps": round(eps, 2),
        "dividend": round(dividend, 2),
        "per": round(per, 2),
        "dividend_yield_percent": round(dividend_yield, 2),
    }


@mcp.tool()
def calculate_pbr(
    price: float,
    bps: float | None = None,
    shareholders_equity: float | None = None,
    shares_outstanding_fy: float | None = None,
    treasury_shares_fy: float | None = None,
) -> dict:
    """株価とBPSからPBRを計算する。BPSが None の場合は自己資本と発行済株式数(自己株式除く)から算出する。"""
    if price <= 0:
        raise ValueError("price は 0 より大きい値である必要があります")

    if bps is None:
        if (
            shareholders_equity is None
            or shares_outstanding_fy is None
            or treasury_shares_fy is None
        ):
            raise ValueError(
                "bps が None の場合は shareholders_equity, shares_outstanding_fy, "
                "treasury_shares_fy をすべて指定する必要があります"
            )

        outstanding_shares = shares_outstanding_fy - treasury_shares_fy
        if outstanding_shares <= 0:
            raise ValueError(
                "shares_outstanding_fy - treasury_shares_fy は 0 より大きい値である必要があります"
            )

        bps = shareholders_equity / outstanding_shares

    if bps <= 0:
        raise ValueError("bps は 0 より大きい値である必要があります")

    pbr = price / bps

    return {
        "price": round(price, 2),
        "bps": round(bps, 2),
        "pbr": round(pbr, 2),
    }


def _safe_per(price, eps):
    """株価とEPSからPERを計算する。値が不正/未取得の場合は None を返す(例外は投げない)。"""
    if price is None or eps is None or price <= 0 or eps <= 0:
        return None
    return round(price / eps, 2)


def _safe_dividend_yield_percent(price, dividend):
    """株価と配当からの配当利回り(%)を計算する。値が不正/未取得の場合は None を返す。"""
    if price is None or dividend is None or price <= 0 or dividend < 0:
        return None
    return round(dividend / price * 100, 2)


def _resolve_bps(bps, shareholders_equity, shares_outstanding_fy, treasury_shares_fy):
    """BPSをAPI値優先で解決する。

    API から取得した bps があればそれを優先し、"api" を出所として返す。
    bps が None の場合は自己資本 / (発行済株式数 - 自己株式数) で算出し、
    "calculated" を出所として返す。どちらも計算できない場合は (None, None) を返す。
    """
    if bps is not None and bps > 0:
        return bps, "api"

    if (
        shareholders_equity is not None
        and shares_outstanding_fy is not None
        and treasury_shares_fy is not None
    ):
        outstanding_shares = shares_outstanding_fy - treasury_shares_fy
        if outstanding_shares > 0:
            return shareholders_equity / outstanding_shares, "calculated"

    return None, None


def _safe_pbr(price, bps):
    """株価とBPSからPBRを計算する。値が不正/未取得の場合は None を返す。"""
    if price is None or bps is None or price <= 0 or bps <= 0:
        return None
    return round(price / bps, 2)


def _safe_operating_margin_percent(operating_profit, revenue):
    """営業利益率(%)を計算する。値が不正/未取得の場合は None を返す(例外は投げない)。"""
    if operating_profit is None or revenue is None or revenue <= 0:
        return None
    return round(operating_profit / revenue * 100, 2)


def _build_investment_observations(
    per,
    pbr,
    roe,
    dividend_yield_percent,
    operating_margin_percent,
) -> dict:
    """PER・PBR・ROE・配当利回り・営業利益率の数値から、投資判断の材料となる観点を整理する。

    単一指標のみからの断定(PERが低い=割安、PBRが1倍未満=割安、等)は行わず、
    「買い」「売り」といった最終的な投資判断も行わない。業種平均や過去複数期の
    推移は取得していないため、その限界を limitations に明記する。
    """
    valuation = []
    risks = []
    strengths = []

    if per is not None:
        level = "低め" if per < 15 else "高め" if per > 15 else "同程度"
        valuation.append(
            f"PERは{per}倍です。市場で目安とされることが多い水準(概ね15倍前後)と比べると{level}ですが、"
            "成長期待や業種によって適正水準は異なるため、これのみで割安・割高とは断定できません。"
        )
    else:
        valuation.append(
            "PERは算出できませんでした(株価またはEPSが取得できない、もしくはEPSが0以下の可能性があります)。"
        )

    if pbr is not None:
        if pbr < 1:
            valuation.append(
                f"PBRは{pbr}倍で1倍を下回っています。純資産と比較した株価水準は相対的に低いとも見えますが、"
                "資産の収益性や将来の資本効率の見通し次第でもあり、これのみで割安とは断定できません。"
            )
        else:
            valuation.append(
                f"PBRは{pbr}倍です。市場が純資産以上の価値を織り込んでいるとも読めますが、"
                "これのみで割高とは断定できません。"
            )
    else:
        valuation.append("PBRは算出できませんでした(株価またはBPSが取得できない可能性があります)。")

    profitability = []
    if roe is not None:
        roe_percent = round(roe * 100, 2)
        profitability.append(
            f"ROEは{roe_percent}%です。一般に8〜10%程度が一つの目安とされますが、業種による差が大きい指標です。"
        )
    else:
        roe_percent = None
        profitability.append("ROEは取得できませんでした。")

    if operating_margin_percent is not None:
        profitability.append(
            f"営業利益率は{operating_margin_percent}%です。業種による水準差が大きいため、"
            "同業他社や過去の推移と比較しないと良し悪しは判断できません。"
        )
    else:
        profitability.append(
            "営業利益率は算出できませんでした(営業利益または売上高が取得できない可能性があります)。"
        )

    shareholder_return = []
    if dividend_yield_percent is not None:
        note = "市場平均と比べて高めの水準とも言えますが、" if dividend_yield_percent >= 3 else ""
        shareholder_return.append(
            f"配当利回りは{dividend_yield_percent}%です。{note}"
            "配当性向やフリーキャッシュフローの推移は未取得のため、この水準が今後も維持できるかは別途確認が必要です。"
        )
    else:
        shareholder_return.append(
            "配当利回りは算出できませんでした(株価または配当が取得できない可能性があります)。"
        )

    if roe_percent is not None and roe_percent >= 10:
        strengths.append("ROEが10%以上であり、自己資本に対する収益効率は比較的高い水準にあるとも読み取れます。")
    if dividend_yield_percent is not None and dividend_yield_percent >= 3:
        strengths.append("配当利回りが3%以上であり、株主還元の観点では相対的に高めの水準です。")
    if pbr is not None and pbr < 1:
        strengths.append("PBRが1倍を下回っており、純資産と比較した株価水準は相対的に低いとも見えます(要因の精査は必要です)。")

    if roe_percent is not None and roe_percent < 5:
        risks.append("ROEが5%未満であり、資本効率の面では改善余地があるとも考えられます。")
    if per is None and pbr is None:
        risks.append("PER・PBRがいずれも算出できず、バリュエーション面の評価材料が不足しています。")
    if operating_margin_percent is not None and operating_margin_percent < 5:
        risks.append("営業利益率が5%を下回っており、本業の収益性が相対的に低い可能性があります(業種要因の可能性もあります)。")

    limitations = [
        "業種平均との比較データは取得していません。",
        "PER・PBR・ROE・配当利回り・営業利益率などの単年度の指標は直近1期分の財務データに基づく整理です。"
        "トレンド(増収・増益や配当の傾向等)は取得できた複数期のデータを用いていますが、"
        "J-Quants APIの提供範囲により取得できる年数が少ない場合があります。"
        "また、一時的な要因や決算資料の定性的な情報までは踏み込んで分析していません。",
        "本ツールは数値の整理と観点の提示のみを行うものであり、「買い」「売り」等の最終的な投資判断は行いません。",
    ]

    return {
        "valuation": valuation,
        "profitability": profitability,
        "shareholder_return": shareholder_return,
        "strengths": strengths,
        "risks": risks,
        "limitations": limitations,
    }


def _build_trend_observations(trend: dict) -> dict:
    """analyze_financial_trend 相当のトレンド情報(_analyze_financial_trend の戻り値)から、
    強み・懸念点・注記の追加分を整理する内部ヘルパー。

    _build_investment_observations(単年度分析)の結果に追記して使う想定で、
    このヘルパー単体でも「買い」「売り」等の最終的な投資判断は行わない。
    trend_analysis_available が False(取得できた年度数が2年未満)の場合は、
    単年・短期のデータで断定するのを避けるため、追加分なし(空リスト)を返す。
    """
    strengths: list[str] = []
    risks: list[str] = []
    notes: list[str] = []

    if not trend.get("trend_analysis_available"):
        return {"strengths": strengths, "risks": risks, "notes": notes}

    revenue_trend = trend.get("revenue_trend")
    profit_trend = trend.get("profit_trend")
    roe_trend = trend.get("roe_trend")
    dividend_trend = trend.get("dividend_trend")
    years_available = trend.get("years_available")

    if revenue_trend == "増加傾向" and profit_trend == "減少傾向":
        notes.append(
            "直近の推移は売上高が増加する一方で利益は減少しており、いわゆる「増収減益」の傾向が見られます。"
            "コスト増加や一時的な費用計上などが要因となっている可能性がありますが、要因の特定には開示資料側の確認が必要です。"
        )
        risks.append("売上は伸びている一方で利益が減少する傾向にあり、収益性の面で懸念材料となり得ます。")
    elif revenue_trend == "増加傾向" and profit_trend == "増加傾向":
        strengths.append("売上・利益がともに増加する傾向にあり、事業成長の面では強みとなり得ます。")

    if roe_trend == "減少傾向":
        risks.append("ROEが低下する傾向にあり、収益性・資本効率の面で懸念材料となり得ます。")
    elif roe_trend == "増加傾向":
        strengths.append("ROEが改善する傾向にあり、資本効率の面で強みとなり得ます。")

    if dividend_trend == "増加傾向":
        strengths.append("配当が増加する傾向にあり、株主還元の観点では強みとなり得ます。")
    elif dividend_trend == "減少傾向":
        risks.append("配当が減少する傾向にあり、株主還元の観点では懸念材料となり得ます。")

    notes.append(
        f"上記のトレンドは直近{years_available}期分のデータに基づく単純な比較であり、"
        "業種平均との比較や一時的な変動要因までは考慮していません。単年度・短期間のデータのみで"
        "将来の方向性を断定するものではありません。"
    )

    return {"strengths": strengths, "risks": risks, "notes": notes}


def _build_trend_section(trend: dict) -> dict:
    """_analyze_financial_trend の戻り値から、generate_investment_summary の "trend" セクション
    向けに必要な項目だけを抜き出して整理する内部ヘルパー。

    disclosure_date は扱わない(latest_period には fiscal_year_end のみを含める)。
    periods が空(トレンド分析不可)の場合、latest_period は None になる。
    """
    periods = trend.get("periods") or []
    latest_period = None
    if periods:
        latest = periods[-1]
        latest_period = {
            "fiscal_year_end": latest.get("fiscal_year_end"),
            "revenue_growth_percent": latest.get("revenue_growth_percent"),
            "operating_profit_growth_percent": latest.get("operating_profit_growth_percent"),
            "profit_growth_percent": latest.get("profit_growth_percent"),
            "eps_growth_percent": latest.get("eps_growth_percent"),
            "roe_change_percent_points": latest.get("roe_change_percent_points"),
            "dividend_change_yen": latest.get("dividend_change_yen"),
            "dividend_growth_percent": latest.get("dividend_growth_percent"),
            "operating_margin_percent": latest.get("operating_margin_percent"),
        }

    return {
        "comparison_type": trend.get("comparison_type"),
        "years_available": trend.get("years_available"),
        "revenue_trend": trend.get("revenue_trend"),
        "profit_trend": trend.get("profit_trend"),
        "profitability_trend": trend.get("profitability_trend"),
        "roe_trend": trend.get("roe_trend"),
        "dividend_trend": trend.get("dividend_trend"),
        "latest_period": latest_period,
    }


_INVESTMENT_SUMMARY_TREND_YEARS = 5


@mcp.tool()
def generate_investment_summary(code: str) -> dict:
    """日本株の銘柄コードから、PER・PBR・ROE・配当利回り・営業利益率などをもとに
    投資判断の材料となる観点(割安性・収益性・株主還元・強み・懸念点)を整理する。
    あわせて analyze_financial_trend 相当の年次財務トレンド("trend")も統合する。
    最終的な投資判断(買い/売り)は行わない。
    """
    if not code:
        raise ValueError("code must not be empty")

    stock = _fetch_japanese_stock_info(code)

    # 単年度指標(financial)と年次トレンド(trend)はどちらも J-Quants の fins/summary を
    # 参照するため、生データを1回だけ取得して使い回し、APIへの重複呼び出しを避ける。
    raw_statements = _fetch_raw_financial_statements(code, error_label="財務情報")
    financial = _fetch_financial_metrics(code, statements=raw_statements)
    history = _fetch_financial_history(
        code, years=_INVESTMENT_SUMMARY_TREND_YEARS, statements=raw_statements
    )
    trend = _analyze_financial_trend(
        code, years=_INVESTMENT_SUMMARY_TREND_YEARS, history=history
    )

    close = stock.get("close")
    eps = financial.get("eps")
    dividend = financial.get("dividend")
    revenue = financial.get("revenue")
    operating_profit = financial.get("operating_profit")
    roe = financial.get("roe")

    bps, bps_source = _resolve_bps(
        bps=financial.get("bps"),
        shareholders_equity=financial.get("shareholders_equity"),
        shares_outstanding_fy=financial.get("shares_outstanding_fy"),
        treasury_shares_fy=financial.get("treasury_shares_fy"),
    )

    per = _safe_per(close, eps)
    pbr = _safe_pbr(close, bps)
    dividend_yield_percent = _safe_dividend_yield_percent(close, dividend)
    operating_margin_percent = _safe_operating_margin_percent(operating_profit, revenue)

    observations = _build_investment_observations(
        per=per,
        pbr=pbr,
        roe=roe,
        dividend_yield_percent=dividend_yield_percent,
        operating_margin_percent=operating_margin_percent,
    )

    trend_additions = _build_trend_observations(trend)
    observations["strengths"] = observations["strengths"] + trend_additions["strengths"]
    observations["risks"] = observations["risks"] + trend_additions["risks"]
    observations["limitations"] = observations["limitations"] + trend_additions["notes"]

    return {
        "code": stock.get("code", code),
        "stock_date": stock.get("date"),
        "close": close,
        "financial_date": financial.get("date"),
        "revenue": revenue,
        "operating_profit": operating_profit,
        "profit": financial.get("profit"),
        "eps": eps,
        "roe": roe,
        "dividend": dividend,
        "bps": round(bps, 2) if bps is not None else None,
        "bps_source": bps_source,
        "per": per,
        "pbr": pbr,
        "dividend_yield_percent": dividend_yield_percent,
        "operating_margin_percent": operating_margin_percent,
        "observations": observations,
        "trend": _build_trend_section(trend),
    }


@mcp.tool()
def analyze_japanese_stock(code: str) -> dict:
    """日本株の銘柄コードから株価と財務情報を取得し、PER・PBR・配当利回りなどを総合分析する。"""
    if not code:
        raise ValueError("code must not be empty")

    stock = _fetch_japanese_stock_info(code)
    financial = _fetch_financial_metrics(code)

    close = stock.get("close")
    eps = financial.get("eps")
    dividend = financial.get("dividend")

    bps, bps_source = _resolve_bps(
        bps=financial.get("bps"),
        shareholders_equity=financial.get("shareholders_equity"),
        shares_outstanding_fy=financial.get("shares_outstanding_fy"),
        treasury_shares_fy=financial.get("treasury_shares_fy"),
    )

    return {
        "code": stock.get("code", code),
        "stock_date": stock.get("date"),
        "close": close,
        "financial_date": financial.get("date"),
        "revenue": financial.get("revenue"),
        "operating_profit": financial.get("operating_profit"),
        "profit": financial.get("profit"),
        "eps": eps,
        "roe": financial.get("roe"),
        "dividend": dividend,
        "bps": round(bps, 2) if bps is not None else None,
        "per": _safe_per(close, eps),
        "pbr": _safe_pbr(close, bps),
        "dividend_yield_percent": _safe_dividend_yield_percent(close, dividend),
        "bps_source": bps_source,
    }


_COMPARISON_TREND_YEARS = 5


def _extreme_code(stocks: list[dict], key: str, mode: str):
    """指定した指標(key)について、値がNoneの銘柄を除外したうえで
    最小値/最大値(mode: "min" または "max")を持つ銘柄コードを返す。
    候補が1つもない場合は None を返す。
    """
    candidates = [s for s in stocks if s.get(key) is not None]
    if not candidates:
        return None
    picker = min if mode == "min" else max
    best = picker(candidates, key=lambda s: s[key])
    return best["code"]


def _compare_japanese_stock(code: str) -> dict:
    """1銘柄分の比較用データ(指標・トレンド)を取得する内部ヘルパー。

    compare_japanese_stocks から銘柄ごとに呼び出される。既存の
    _fetch_japanese_stock_info / _fetch_raw_financial_statements /
    _fetch_financial_metrics / _fetch_financial_history / _analyze_financial_trend
    を再利用し、財務諸表の生データ(raw_statements)は同一銘柄内で使い回すことで
    J-Quants APIへの重複呼び出しを避ける(generate_investment_summary と同じ方針)。
    取得・計算に失敗した銘柄は例外を投げず、error に理由を格納し、指標・トレンドは
    None(またはトレンドのみ「判定不可」)として返す(他の銘柄の比較を継続できるようにするため)。

    years_available / comparison_type は、compare_japanese_stocks 側で
    trend_summary(前年比較 or 複数年トレンドの文言)を組み立てる際に使う
    (_analyze_financial_trend が既に算出している値をそのまま転記するのみで、
    判定ロジック自体はここで重複させない)。
    """
    try:
        stock = _fetch_japanese_stock_info(code)
        raw_statements = _fetch_raw_financial_statements(code, error_label="財務情報")
        financial = _fetch_financial_metrics(code, statements=raw_statements)
        history = _fetch_financial_history(
            code, years=_COMPARISON_TREND_YEARS, statements=raw_statements
        )
        trend = _analyze_financial_trend(
            code, years=_COMPARISON_TREND_YEARS, history=history
        )
    except ValueError as e:
        return {
            "code": code,
            "error": str(e),
            "stock_date": None,
            "close": None,
            "financial_date": None,
            "per": None,
            "pbr": None,
            "roe": None,
            "dividend_yield_percent": None,
            "operating_margin_percent": None,
            "trend_analysis_available": False,
            "years_available": 0,
            "comparison_type": "分析不可",
            "revenue_trend": "判定不可",
            "profit_trend": "判定不可",
            "profitability_trend": "判定不可",
            "roe_trend": "判定不可",
            "dividend_trend": "判定不可",
        }

    close = stock.get("close")
    eps = financial.get("eps")
    dividend = financial.get("dividend")
    revenue = financial.get("revenue")
    operating_profit = financial.get("operating_profit")
    roe = financial.get("roe")

    bps, _bps_source = _resolve_bps(
        bps=financial.get("bps"),
        shareholders_equity=financial.get("shareholders_equity"),
        shares_outstanding_fy=financial.get("shares_outstanding_fy"),
        treasury_shares_fy=financial.get("treasury_shares_fy"),
    )

    return {
        "code": stock.get("code", code),
        "error": None,
        "stock_date": stock.get("date"),
        "close": close,
        "financial_date": financial.get("date"),
        "per": _safe_per(close, eps),
        "pbr": _safe_pbr(close, bps),
        "roe": roe,
        "dividend_yield_percent": _safe_dividend_yield_percent(close, dividend),
        "operating_margin_percent": _safe_operating_margin_percent(
            operating_profit, revenue
        ),
        "trend_analysis_available": trend.get("trend_analysis_available", False),
        "years_available": trend.get("years_available", 0),
        "comparison_type": trend.get("comparison_type", "分析不可"),
        "revenue_trend": trend.get("revenue_trend", "判定不可"),
        "profit_trend": trend.get("profit_trend", "判定不可"),
        "profitability_trend": trend.get("profitability_trend", "判定不可"),
        "roe_trend": trend.get("roe_trend", "判定不可"),
        "dividend_trend": trend.get("dividend_trend", "判定不可"),
    }


def _rank_stocks(stocks: list[dict], key: str, ascending: bool) -> list[dict]:
    """指定した指標(key)について、値が None の銘柄を除外したうえでランキングする内部ヘルパー。

    ascending=True なら昇順(値が低い順。PER/PBR向け)、
    ascending=False なら降順(値が高い順。ROE/営業利益率/配当利回り向け)で並べる。
    戻り値は [{"code": ..., "value": ...}, ...] 形式。
    """
    candidates = [s for s in stocks if s.get(key) is not None]
    ordered = sorted(candidates, key=lambda s: s[key], reverse=not ascending)
    return [{"code": s["code"], "value": s[key]} for s in ordered]


def _rank_position(ranking: list[dict], code: str):
    """_rank_stocks の戻り値(ranking)の中から code の順位(1始まり)とランキング対象の
    総数を (rank, total) で返す。code が ranking に含まれない(値が None で除外された、
    または取得エラー)場合は None を返す。
    """
    for index, entry in enumerate(ranking):
        if entry["code"] == code:
            return index + 1, len(ranking)
    return None


def _build_valuation_summary(
    stock: dict, per_ranking: list[dict], pbr_ranking: list[dict], n_stocks: int
) -> str:
    """PER・PBRについて、比較対象内での相対的な位置づけを整理したサマリー文を組み立てる。

    「順位が高い(低PER/低PBR)=割安」という断定はせず、あくまで比較対象n_stocks銘柄内での
    相対的な順位の提示にとどめる。
    """
    code = stock["code"]
    parts = []

    per = stock.get("per")
    per_pos = _rank_position(per_ranking, code)
    if per is not None and per_pos:
        rank, total = per_pos
        parts.append(f"PERは{per}倍で、データを取得できた{total}銘柄中{rank}位(低い順)です。")
    else:
        parts.append("PERは算出できませんでした。")

    pbr = stock.get("pbr")
    pbr_pos = _rank_position(pbr_ranking, code)
    if pbr is not None and pbr_pos:
        rank, total = pbr_pos
        parts.append(f"PBRは{pbr}倍で、データを取得できた{total}銘柄中{rank}位(低い順)です。")
    else:
        parts.append("PBRは算出できませんでした。")

    parts.append(
        f"これは比較対象{n_stocks}銘柄内での相対比較であり、順位が高い(数値が低い)ことが"
        "そのまま割安であることを意味するものではありません。"
    )
    return "".join(parts)


def _build_profitability_summary(
    stock: dict,
    roe_ranking: list[dict],
    operating_margin_ranking: list[dict],
    n_stocks: int,
) -> str:
    """ROE・営業利益率について、比較対象内での相対的な位置づけを整理したサマリー文を組み立てる。"""
    code = stock["code"]
    parts = []

    roe = stock.get("roe")
    roe_pos = _rank_position(roe_ranking, code)
    if roe is not None and roe_pos:
        rank, total = roe_pos
        roe_percent = round(roe * 100, 2)
        parts.append(f"ROEは{roe_percent}%で、データを取得できた{total}銘柄中{rank}位(高い順)です。")
    else:
        parts.append("ROEは算出できませんでした。")

    operating_margin_percent = stock.get("operating_margin_percent")
    operating_margin_pos = _rank_position(operating_margin_ranking, code)
    if operating_margin_percent is not None and operating_margin_pos:
        rank, total = operating_margin_pos
        parts.append(
            f"営業利益率は{operating_margin_percent}%で、データを取得できた{total}銘柄中{rank}位(高い順)です。"
        )
    else:
        parts.append("営業利益率は算出できませんでした。")

    parts.append(
        f"これは比較対象{n_stocks}銘柄内での相対比較であり、事業構成や業種特性の違いは考慮していません。"
    )
    return "".join(parts)


def _build_shareholder_return_summary(
    stock: dict, dividend_yield_ranking: list[dict], n_stocks: int
) -> str:
    """配当利回りについて、比較対象内での相対的な位置づけを整理したサマリー文を組み立てる。"""
    code = stock["code"]
    parts = []

    dividend_yield_percent = stock.get("dividend_yield_percent")
    dividend_pos = _rank_position(dividend_yield_ranking, code)
    if dividend_yield_percent is not None and dividend_pos:
        rank, total = dividend_pos
        parts.append(
            f"配当利回りは{dividend_yield_percent}%で、データを取得できた{total}銘柄中{rank}位(高い順)です。"
        )
    else:
        parts.append("配当利回りは算出できませんでした。")

    parts.append(
        f"これは比較対象{n_stocks}銘柄内での相対比較です。配当性向やフリーキャッシュフローの推移は"
        "未取得のため、この利回りが今後も維持できるかは別途確認が必要です。"
    )
    return "".join(parts)


def _build_trend_summary(stock: dict) -> str:
    """財務トレンド(売上・利益・収益性・ROE・配当)を整理したサマリー文を組み立てる。

    stock["comparison_type"](_analyze_financial_trend が算出済みの値。取得できた年度数が
    2年のみの場合は「前年比較」、それ以上なら「複数年トレンド」)をそのまま使う。
    """
    if not stock.get("trend_analysis_available"):
        return "財務トレンドを分析するためのデータが不足しているため、判定できませんでした。"

    comparison_type = stock.get("comparison_type") or "トレンド比較"
    return (
        f"直近の{comparison_type}では、売上は{stock.get('revenue_trend')}、"
        f"利益は{stock.get('profit_trend')}、収益性は{stock.get('profitability_trend')}、"
        f"ROEは{stock.get('roe_trend')}、配当は{stock.get('dividend_trend')}という結果でした。"
        "業種平均との比較や一時的な変動要因は考慮していません。"
    )


@mcp.tool()
def compare_japanese_stocks(codes: list[str]) -> dict:
    """日本株の銘柄コードを2〜5件指定して、PER・PBR・ROE・配当利回り・営業利益率と、
    可能であれば直近の財務トレンド(増収・増益・収益性・ROE・配当の傾向)を横並びで比較する。

    各銘柄の指標・トレンドは既存のヘルパーを再利用して取得する。「PERが最も低い=最も割安」
    のような単一指標での断定は行わず、事業構成・成長期待・財務体質などの違いを考慮していない
    単純比較であることを comparison.notes に明記する。最終的な投資判断(買い/売り)は行わない。
    """
    if not codes:
        raise ValueError("codes must not be empty")
    if not 2 <= len(codes) <= 5:
        raise ValueError("codes は 2〜5件で指定してください")

    stocks = [_compare_japanese_stock(code) for code in codes]
    n_stocks = len(stocks)

    per_ranking = _rank_stocks(stocks, "per", ascending=True)
    pbr_ranking = _rank_stocks(stocks, "pbr", ascending=True)
    roe_ranking = _rank_stocks(stocks, "roe", ascending=False)
    operating_margin_ranking = _rank_stocks(stocks, "operating_margin_percent", ascending=False)
    dividend_yield_ranking = _rank_stocks(stocks, "dividend_yield_percent", ascending=False)

    # 銘柄ごとに4軸(割安性・収益性・株主還元・トレンド)の比較サマリーを付与する。
    # ランキングは全銘柄が揃って初めて計算できるため、_compare_japanese_stock 内ではなく
    # ここ(全銘柄を集めた後)で組み立てる。
    for stock in stocks:
        stock["valuation_summary"] = _build_valuation_summary(
            stock, per_ranking, pbr_ranking, n_stocks
        )
        stock["profitability_summary"] = _build_profitability_summary(
            stock, roe_ranking, operating_margin_ranking, n_stocks
        )
        stock["shareholder_return_summary"] = _build_shareholder_return_summary(
            stock, dividend_yield_ranking, n_stocks
        )
        stock["trend_summary"] = _build_trend_summary(stock)

    comparison = {
        "lowest_per_code": _extreme_code(stocks, "per", "min"),
        "lowest_pbr_code": _extreme_code(stocks, "pbr", "min"),
        "highest_roe_code": _extreme_code(stocks, "roe", "max"),
        "highest_operating_margin_code": _extreme_code(
            stocks, "operating_margin_percent", "max"
        ),
        "highest_dividend_yield_code": _extreme_code(
            stocks, "dividend_yield_percent", "max"
        ),
        "per_ranking": per_ranking,
        "pbr_ranking": pbr_ranking,
        "roe_ranking": roe_ranking,
        "operating_margin_ranking": operating_margin_ranking,
        "dividend_yield_ranking": dividend_yield_ranking,
        "notes": [
            (
                "各項目の最小値・最大値・ランキングは、その指標を算出・取得できた銘柄のみを対象としており"
                "(値が None の銘柄は除外しています)。"
                "「PERが最も低い=最も割安」「PBRが最も低い=最も割安」のような単一指標での断定はできません。"
                "あくまで比較対象内での相対比較であり、事業構成・成長期待・財務体質などの違いは考慮していません。"
            ),
            (
                f"各銘柄の valuation_summary / profitability_summary / shareholder_return_summary / "
                f"trend_summary は、いずれも比較対象{n_stocks}銘柄内での相対的な位置づけを示すもので、"
                "投資判断(買い/売り)を行うものではありません。"
            ),
        ],
    }

    return {
        "stocks": stocks,
        "comparison": comparison,
    }


@mcp.resource("finance://notes", name="finance-notes")
def finance_notes() -> str:
    """投資判断の際に参照する基本的なメモ。"""
    return (
        "投資判断では、PER・PBR・ROE・配当利回りを確認する。\n"
        "為替を見るときは取得日も確認する。"
    )


@mcp.prompt()
def finance_analysis(company_name: str) -> str:
    """指定した企業の投資判断の観点を整理するためのプロンプト。"""
    return (
        f"{company_name} について、PER・PBR・ROE・配当利回りを確認し、\n"
        "必要に応じて為替情報も確認して、投資判断の観点を整理してください。"
    )


if __name__ == "__main__":
    mcp.run()
