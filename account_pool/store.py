# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Account storage: a JSON file (default ``data/accounts/accounts.json``).

Accounts can be imported in bulk from CSV / Excel / JSON with the columns
``platform, account_name, cookies, proxy, remark`` (only platform and cookies
are required).
"""
import csv
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import AccountInfo, AccountStatus

IMPORT_FIELDS = ("id", "platform", "account_name", "cookies", "proxy", "remark")


class AccountStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.RLock()

    # ---------------- persistence ----------------
    def load(self) -> List[AccountInfo]:
        with self._lock:
            if not self.path.exists():
                return []
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [AccountInfo(**item) for item in raw.get("accounts", [])]

    def save(self, accounts: Iterable[AccountInfo]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"accounts": [a.model_dump(mode="json") for a in accounts]}
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".accounts_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

    # ---------------- CRUD ----------------
    def list(self, platform: Optional[str] = None) -> List[AccountInfo]:
        accounts = self.load()
        return [a for a in accounts if platform is None or a.platform == platform]

    def get(self, account_id: str) -> Optional[AccountInfo]:
        return next((a for a in self.load() if a.id == account_id), None)

    def upsert(self, account: AccountInfo) -> AccountInfo:
        with self._lock:
            accounts = self.load()
            for i, a in enumerate(accounts):
                if a.id == account.id:
                    accounts[i] = account
                    break
            else:
                accounts.append(account)
            self.save(accounts)
            return account

    def add_many(self, new_accounts: Iterable[AccountInfo]) -> int:
        """Add accounts, skipping ones whose (platform, cookies) already exist."""
        with self._lock:
            accounts = self.load()
            known = {(a.platform, a.cookies) for a in accounts}
            ids = {a.id for a in accounts}
            added = 0
            for acc in new_accounts:
                if (acc.platform, acc.cookies) in known or acc.id in ids:
                    continue
                accounts.append(acc)
                known.add((acc.platform, acc.cookies))
                ids.add(acc.id)
                added += 1
            self.save(accounts)
            return added

    def remove(self, account_id: str) -> bool:
        with self._lock:
            accounts = self.load()
            left = [a for a in accounts if a.id != account_id]
            if len(left) == len(accounts):
                return False
            self.save(left)
            return True

    def reset(self, account_id: str) -> Optional[AccountInfo]:
        """Clear failures/cooldown and mark the account usable again."""
        with self._lock:
            acc = self.get(account_id)
            if acc is None:
                return None
            acc.status = AccountStatus.NORMAL
            acc.fail_count = 0
            acc.cooling_until = 0
            acc.last_error = ""
            return self.upsert(acc)

    # ---------------- import ----------------
    @staticmethod
    def parse_rows(rows: Iterable[Dict]) -> List[AccountInfo]:
        result = []
        for n, row in enumerate(rows, start=1):
            data = {k: ("" if row.get(k) is None else str(row.get(k)).strip())
                    for k in IMPORT_FIELDS if k in row}
            if not data.get("id"):
                data.pop("id", None)
            if not any(data.values()):
                continue
            try:
                result.append(AccountInfo(**data))
            except ValueError as e:
                raise ValueError(f"第 {n} 行数据无效: {e}") from e
        return result

    @classmethod
    def read_import_file(cls, file_path: str) -> List[AccountInfo]:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".csv":
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                return cls.parse_rows(csv.DictReader(f))
        if suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("accounts", [])
            return cls.parse_rows(data)
        if suffix in (".xlsx", ".xlsm"):
            from openpyxl import load_workbook

            wb = load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not rows:
                return []
            header = [str(h).strip() if h is not None else "" for h in rows[0]]
            return cls.parse_rows(dict(zip(header, r)) for r in rows[1:])
        raise ValueError(f"不支持的文件类型: {suffix}（支持 .csv / .xlsx / .json）")
