[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "luxury-fashion"
version = "1.0.0"
description = "Luxury Fashion E‑Commerce Backend"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
where = ["."]
include = ["app", "app.*"]