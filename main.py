#!/usr/bin/env python3

import os
from dataclasses import dataclass
import json
import poplib
import time
import sqlite3
import urllib.request


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


def migrate(db):
    c = db.cursor()
    c.execute(
        """
CREATE TABLE IF NOT EXISTS history (
    id INT PRIMARY KEY,
    mail_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mail_id)
);
"""
    )
    db.commit()


def lookup(db, mail_id):
    c = db.cursor()
    c.execute("SELECT 1 FROM history WHERE mail_id=? LIMIT 1", (mail_id,))
    if c.fetchone():
        return True
    return False


def update_db(db, mail_id):
    c = db.cursor()
    c.execute("INSERT INTO history (mail_id) VALUES (?)", (mail_id,))
    db.commit()


def send_code(webhook, code):
    data = {"text": f"Fellow tapirs, here's the latest login code {code}"}
    req = urllib.request.Request(
        url=webhook,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req)


def main():
    config = get_config()

    db = sqlite3.connect("history.db")
    migrate(db)

    mailer = poplib.POP3_SSL(config.pop3_server, config.pop3_port)
    mailer.user(config.pop3_account)
    mailer.pass_(config.pop3_password)

    while True:
        print("fetching new emails")
        mails = mailer.list()
        if len(mails) > 1:
            for i, mail_id in map(lambda m: m.split(), mails[1]):
                if not lookup(db, mail_id):
                    print("found new email")
                    status, content, _ = mailer.retr(int(i))

                    if status == b"+OK":
                        print("status passed")
                        confirmed = 0
                        cursor = 0
                        count = len(content)

                        for row_id in range(count):
                            row = content[row_id]
                            if row == b"From: yourfriends@streamyard.com":
                                confirmed += 1
                                continue

                            if row == b"Subject: StreamYard Login Code":
                                confirmed += 1
                                continue

                            if confirmed == 2:
                                cursor = row_id
                                break

                        if confirmed != 2:
                            print("not from streamyard")
                            continue

                        for row_id in range(cursor, count):
                            row = content[row_id]
                            if row == b"Here is your login code for StreamYard:":
                                print("found a new code")
                                target = row_id + 2
                                if target < count:
                                    code = content[target]
                                    send_code(
                                        config.slack_webhook, code.decode("utf-8")
                                    )
                                    update_db(db, mail_id)
                                break
        print("back to sleep")
        time.sleep(60)
    db.close()


if __name__ == "__main__":
    main()
