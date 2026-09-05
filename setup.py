from setuptools import setup, find_packages

setup(
    name="the-extractor",
    version="2.5.0",
    description="A modern, cross-platform media downloader, tag inspector, transcript generator, and audio preparation suite",
    author="Muhammed Sahil Subair",
    packages=find_packages(),
    py_modules=["server", "downloader", "config", "database", "main"],
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.28.0",
        "pydantic>=2.0.0",
        "yt-dlp>=2024.0.0",
        "youtube-transcript-api>=0.6.0",
        "pyyaml>=6.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "the-extractor=main:main",
            "extractor=main:main",
        ],
    },
    include_package_data=True,
    python_requires=">=3.10",
)
