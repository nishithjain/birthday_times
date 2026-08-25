# setup.py
"""Setup configuration for Birthday Chronicles."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="birthday-chronicles",
    version="0.3.0",
    author="Birthday Chronicles Team",
    description="A personalized historical chronicle for your birthday",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/birthday-chronicles",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.32.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "web": [
            "flask>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "birthday-chronicles=backend.app:main",
        ],
    },
)