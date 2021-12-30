#!/usr/bin/env python3

import os
from dataclasses import dataclass
import json
import logging
import poplib
import time
import sqlite3
import urllib.request

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(handler)


@dataclass
class Config:
    pop3_server: str
    pop3_port: int
    pop3_account: str
    pop3_password: str
    slack_webhook: str


def get_config():
    pop3_server = os.environ.get("POP3_SERVER")
    if not pop3_server:
        raise Exception("required POP3_SERVER not found")

    pop3_port = os.environ.get("POP3_PORT")
    if not pop3_port:
        raise Exception("required POP3_PORT not found")

    pop3_account = os.environ.get("POP3_ACCOUNT")
    if not pop3_account:
        raise Exception("required POP3_ACCOUNT not found")

    pop3_password = os.environ.get("POP3_PASSWORD")
    if not pop3_password:
        raise Exception("required POP3_PASSWORD not found")

    slack_webhook = os.environ.get("SLACK_WEBHOOK")
    if not slack_webhook:
        raise Exception("required SLACK_WEBHOOK not found")

    return Config(
        pop3_server, int(pop3_port), pop3_account, pop3_password, slack_webhook,
    )


class Database:
    def __init__(self, path):
        self.db = sqlite3.connect("history.db")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def migrate(self):
        c = self.db.cursor()
        c.execute(
            """
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY,
        mail_id TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(mail_id)
    );
    """
        )
        self.db.commit()

    def check(self, mail_id):
        c = self.db.cursor()
        c.execute("SELECT 1 FROM history WHERE mail_id=? LIMIT 1", (mail_id,))
        if c.fetchone():
            return True
        return False

    def insert(self, mail_id):
        c = self.db.cursor()
        c.execute("INSERT INTO history (mail_id) VALUES (?)", (mail_id,))
        self.db.commit()


def send_code(webhook, code):
    data = {"text": f"Fellow tapirs, here's the latest login code {code}"}
    req = urllib.request.Request(
        url=webhook,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req)


class Mailer:
    def __init__(self, db, config):
        mailer = poplib.POP3_SSL(config.pop3_server, config.pop3_port)
        mailer.user(config.pop3_account)
        mailer.pass_(config.pop3_password)
        self.mailer = mailer
        self.db = db

    def __enter__(self):
        mails = self.mailer.list()
        if len(mails) != 3:
            return []

        for i, mail_id in map(lambda m: m.split(), mails[1]):
            if self.db.check(mail_id):
                continue

            status, content, _ = self.mailer.retr(int(i))
            if status != b"+OK":
                continue

            cursor = 0
            confirmed = 0
            count = len(content)

            for row_id in range(count):
                row = content[row_id]
                if row == b"From: Your Friends <yourfriends@streamyard.com>":
                    confirmed += 1
                    continue

                if row == b"Subject: StreamYard Login Code":
                    confirmed += 1
                    continue

                if confirmed == 2:
                    cursor = row_id
                    break

            if confirmed != 2:
                self.db.insert(mail_id)
                continue

            for row_id in range(cursor, count):
                row = content[row_id]
                if row == b'Your login code is:':
                    target = row_id + 2
                    if target < count:
                        code = content[target]
                        yield code
                        self.mailer.dele(int(i))
                        self.db.insert(mail_id)
                    break

    def __exit__(self, *args):
        self.mailer.quit()

def main():
    log.info("program started")

    config = get_config()

    with Database("history.db") as db:
        log.info("connected to db")
        db.migrate()

        while True:
            # log.debug("fetching email")
            with Mailer(db, config) as mails:
                for code in mails:
                    c = code.decode("utf-8")
                    log.debug(f"found a new code {c}")
                    send_code(config.slack_webhook, c)
            # log.debug("back to sleep")
            time.sleep(30)


if __name__ == "__main__":
    main()
