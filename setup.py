from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

## Edit below variables as per your requirements 

REPO_NAME = "Book Recmmandation System"
AUTHOR_USER_NAME = "KAWSAR AHMMED"
SRC_REPO = "books_recommender"
LIST_OF_REQUIREMENTS = []

setup(
    name=SRC_REPO,
    version="0.0.1",
    author="",
    description="A small local packages for ML based books recommendations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kawsar07ahmmed0712-rgb/Book-Recommandation-System.git",
    author_email="kawsar07ahmmed0712@gmail.com",
    packages=find_packages(),
    license="MIT",
    python_requires=">=3.7",
    install_requires=LIST_OF_REQUIREMENTS
)