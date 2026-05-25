"""
Setup script for Simple Video Player
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="simple-video-player",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A modern, extensible video player application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/simple-video-player",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Video :: Players",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "video-player=src.main:main",
        ],
    },
)
