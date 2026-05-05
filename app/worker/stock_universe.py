from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_RELATIVE_PATH = Path("config") / "tracked_stocks.csv"
TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


@dataclass(frozen=True)
class TrackedStock:
    symbol: str
    name: str = ""
    exchange: str = ""


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def default_stock_list_path() -> Path:
    module_dir = _module_dir()
    candidates = [
        module_dir / DEFAULT_CONFIG_RELATIVE_PATH,
        Path.cwd() / DEFAULT_CONFIG_RELATIVE_PATH,
    ]

    if len(module_dir.parents) > 1:
        candidates.append(module_dir.parents[1] / DEFAULT_CONFIG_RELATIVE_PATH)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def resolve_stock_list_path(value: str | Path | None = None) -> Path:
    if value is None or str(value).strip() == "":
        return default_stock_list_path()

    path = Path(value).expanduser()
    if path.is_absolute():
        return path

    module_dir = _module_dir()
    candidates = [
        Path.cwd() / path,
        module_dir / path,
    ]
    if len(module_dir.parents) > 1:
        candidates.append(module_dir.parents[1] / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def parse_enabled(value: str | None, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized == "":
        return True
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid enabled value on row {row_number}: {value!r}. "
        "Use true or false."
    )


def load_tracked_stocks(path: str | Path | None = None) -> list[TrackedStock]:
    stock_list_path = resolve_stock_list_path(path)
    if not stock_list_path.exists():
        raise ValueError(f"Tracked stock list not found: {stock_list_path}")

    with stock_list_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"Tracked stock list is empty: {stock_list_path}")

        fields_by_name = {field.strip().lower(): field for field in reader.fieldnames}
        if "symbol" not in fields_by_name:
            raise ValueError(
                f"Tracked stock list must include a symbol column: {stock_list_path}"
            )

        symbol_field = fields_by_name["symbol"]
        name_field = fields_by_name.get("name")
        exchange_field = fields_by_name.get("exchange")
        enabled_field = fields_by_name.get("enabled")

        stocks: list[TrackedStock] = []
        seen_symbols: set[str] = set()

        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"Unexpected extra columns on row {row_number}: {stock_list_path}"
                )

            if not any((value or "").strip() for value in row.values()):
                continue

            symbol = (row.get(symbol_field) or "").strip().upper()
            if not symbol:
                raise ValueError(f"Missing symbol on row {row_number}: {stock_list_path}")

            enabled = parse_enabled(
                row.get(enabled_field) if enabled_field is not None else None,
                row_number,
            )
            if not enabled:
                continue

            if symbol in seen_symbols:
                raise ValueError(
                    f"Duplicate enabled stock symbol {symbol!r} on row {row_number}: "
                    f"{stock_list_path}"
                )

            seen_symbols.add(symbol)
            stocks.append(
                TrackedStock(
                    symbol=symbol,
                    name=(row.get(name_field) or "").strip() if name_field else "",
                    exchange=(row.get(exchange_field) or "").strip()
                    if exchange_field
                    else "",
                )
            )

    if not stocks:
        raise ValueError(f"No enabled stock symbols found in {stock_list_path}")

    return stocks


def load_tracked_symbols(path: str | Path | None = None) -> list[str]:
    return [stock.symbol for stock in load_tracked_stocks(path)]
