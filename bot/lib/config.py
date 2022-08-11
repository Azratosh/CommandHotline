import logging
import os
import pathlib
from typing import *

import yaml


CONFIG_FILE = pathlib.Path("..", "config.yaml")
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
}


class ConfigValueError(ValueError):
    pass


class Config:
    token: Optional[str] = None
    owner_id: Optional[int] = None
    prefix: Optional[str] = None
    mentionable: bool = False
    db_credentials: dict[str, str] = {}
    logging: dict[str, Any] = {}

    @classmethod
    def load(cls, force=False):
        if not force and cls.token is not None:
            return

        config = {**cls.__load_yaml(), **cls.__load_env()}

        mandatory_values = ("token", "prefix")
        mandatory_pg_values = ("database", "user", "password", "host", "port")
        mandatory_log_values = ("level",)

        missing_values = []

        for value in mandatory_values:
            if not config.get(value):
                missing_values.append(value)

        if not config.get("db_credentials"):
            missing_values += list(mandatory_pg_values)
        else:
            for value in mandatory_pg_values:
                if not config.get("db_credentials"):
                    missing_values.append(f"db_credentials.{value}")

        if not config.get("logging"):
            missing_values += list(mandatory_log_values)
        else:
            for value in mandatory_log_values:
                if not config.get("logging"):
                    missing_values.append(f"logging.{value}")

        if missing_values:
            raise ConfigValueError(
                "The following config values are missing: " + ", ".join(missing_values)
            )

        cls.token = str(config["token"])
        cls.owner_id = int(config.get("owner_id") or 0)
        cls.prefix = str(config["prefix"])

        mentionable = config.get("mentionable") or False
        if isinstance(mentionable, str):
            cls.mentionable = mentionable.lower() in ("y", "yes", "true")
        else:
            cls.mentionable = mentionable

        for value in mandatory_pg_values:
            cls.db_credentials[value] = config["db_credentials"][value]

        log_level = config["logging"]["level"]
        if log_level not in LOG_LEVELS:
            raise ConfigValueError(f"Invalid logging level: {log_level}")

        cls.logging["level"] = LOG_LEVELS[log_level]

    @classmethod
    def __load_yaml(cls):
        try:
            with open(CONFIG_FILE, "r") as file:
                return yaml.safe_load(file)

        except FileNotFoundError as e:
            return {}

        except Exception as e:
            logging.error(
                f"Encountered unexpected error while opening {CONFIG_FILE}:",
                exc_info=e,
            )

            return {}

    @classmethod
    def __load_env(cls):
        config = {}

        for env_var, conf_var in {
            "TOKEN": "token",
            "OWNER_ID": "owner_id",
            "PREFIX": "prefix",
            "MENTIONABLE": "mentionable",
        }.items():
            if env_var in os.environ:
                config[conf_var] = os.environ[env_var]

        for env_var, conf_var in {
            "PG_DATABASE": "database",
            "PG_USER": "user",
            "PG_PASSWORD": "password",
            "PG_HOST": "host",
            "PG_PORT": "port",
        }.items():
            if env_var in os.environ:
                if "db_credentials" not in config:
                    config["db_credentials"] = {}
                config["db_credentials"][conf_var] = os.environ[env_var]

        for env_var, conf_var in {
            "LOG_LEVEL": "level",
        }.items():
            if env_var in os.environ:
                if "logging" not in config:
                    config["logging"] = {}
                config["logging"][conf_var] = os.environ[env_var]

        return config


Config.load()
