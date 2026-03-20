import os

BOT_NAME = "nexus_scraper"
SPIDER_MODULES = ["scrapy_project.spiders"]
NEWSPIDER_MODULE = "scrapy_project.spiders"

# Obey robots.txt (set False only for legitimate competitive intelligence)
ROBOTSTXT_OBEY = True

# Concurrent requests
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Delays
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = True

# Autothrottle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Pipelines
ITEM_PIPELINES = {
    "scrapy_project.pipelines.MySQLPipeline": 300,
}

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "scrapy_project.middlewares.RandomUserAgentMiddleware": 400,
    "scrapy_project.middlewares.RetryMiddleware": 550,
}

# MySQL settings (used by pipeline)
MYSQL_HOST = os.environ.get("DB_HOST", "mysql")
MYSQL_PORT = int(os.environ.get("DB_PORT", "3306"))
MYSQL_USER = os.environ.get("DB_USER", "nexus")
MYSQL_PASSWORD = os.environ.get("DB_PASSWORD", "nexus_secret")
MYSQL_DB = os.environ.get("DB_NAME", "nexus_core")

# Logging
LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
