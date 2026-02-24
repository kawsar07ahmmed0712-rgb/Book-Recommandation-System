# Book Recommendation System

A collaborative filtering book recommender with an end-to-end training pipeline and a Flask web application UI.

## Project workflow
- `config/config.yaml`
- `books_recommender/entity`
- `books_recommender/config/configuration.py`
- `books_recommender/components`
- `books_recommender/pipeline`
- `app.py` (Flask web app)

## Setup
1. Create and activate your environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run training pipeline
```bash
python main.py
```

## Run web app
```bash
python app.py
```

Then open: `http://127.0.0.1:5000`
