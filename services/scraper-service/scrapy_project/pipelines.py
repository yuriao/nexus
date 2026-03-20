"""
Scrapy pipeline: save items to MySQL nexus_core.companies_datapoint.
"""
import json
import logging
from datetime import datetime, timezone

import MySQLdb

logger = logging.getLogger(__name__)


class MySQLPipeline:
    def __init__(self, mysql_host, mysql_port, mysql_user, mysql_password, mysql_db):
        self.mysql_host = mysql_host
        self.mysql_port = mysql_port
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_db = mysql_db
        self.connection = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mysql_host=crawler.settings.get("MYSQL_HOST", "mysql"),
            mysql_port=crawler.settings.getint("MYSQL_PORT", 3306),
            mysql_user=crawler.settings.get("MYSQL_USER", "nexus"),
            mysql_password=crawler.settings.get("MYSQL_PASSWORD", "nexus_secret"),
            mysql_db=crawler.settings.get("MYSQL_DB", "nexus_core"),
        )

    def open_spider(self, spider):
        self.connection = MySQLdb.connect(
            host=self.mysql_host,
            port=self.mysql_port,
            user=self.mysql_user,
            passwd=self.mysql_password,
            db=self.mysql_db,
            charset="utf8mb4",
        )
        self.cursor = self.connection.cursor()
        logger.info("MySQL pipeline connected")

    def close_spider(self, spider):
        if self.connection:
            self.connection.close()

    def process_item(self, item, spider):
        try:
            structured = item.get("structured_json")
            self.cursor.execute(
                """INSERT INTO companies_datapoint
                   (company_id, source_type, source_url, raw_text,
                    structured_json, extracted_at, confidence_score)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   raw_text = VALUES(raw_text),
                   structured_json = VALUES(structured_json),
                   extracted_at = VALUES(extracted_at)
                """,
                (
                    item["company_id"],
                    item["source_type"],
                    item["source_url"],
                    item["raw_text"],
                    json.dumps(structured) if structured else None,
                    item.get("extracted_at", datetime.now(timezone.utc)),
                    float(item.get("confidence_score", 1.0)),
                ),
            )
            self.connection.commit()
        except Exception as exc:
            logger.error("MySQL insert failed: %s — item: %s", exc, item)
            self.connection.rollback()
        return item
