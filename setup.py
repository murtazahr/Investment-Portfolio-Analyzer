from setuptools import setup, find_packages

setup(
    name="portfolio-dashboard",
    version="1.0.0",
    description="A Flask-based portfolio analysis dashboard",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "Flask==2.3.3",
        "numpy==1.24.3",
        "pandas==2.0.3",
        "plotly==5.15.0",
        "requests==2.31.0",
        "python-dotenv==1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.0",
            "pytest-cov==4.1.0",
            "black==23.7.0",
            "flake8==6.0.0",
            "mypy==1.5.1",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)