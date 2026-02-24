import os
import pickle
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from books_recommender.config.configuration import AppConfiguration
from books_recommender.exception.exception_handler import AppException
from books_recommender.logger.log import logging
from books_recommender.pipeline.training_pipeline import TrainingPipeline


class RecommendationEngine:
    def __init__(self, app_config: AppConfiguration = AppConfiguration()):
        try:
            self.recommendation_config = app_config.get_recommendation_config()
        except Exception as e:
            raise AppException(e, sys) from e

        self._model = None
        self._book_pivot = None
        self._final_rating = None
        self._book_names: List[str] = []
        self._image_lookup: Dict[str, Optional[str]] = {}
        self._normalized_title_lookup: Dict[str, str] = {}
        self._artifact_mod_times: Dict[str, float] = {}

    def _required_artifacts(self) -> List[str]:
        return [
            self.recommendation_config.trained_model_path,
            self.recommendation_config.book_pivot_serialized_objects,
            self.recommendation_config.final_rating_serialized_objects,
            self.recommendation_config.book_names_serialized_objects,
        ]

    def missing_artifacts(self) -> List[str]:
        return [path for path in self._required_artifacts() if not os.path.exists(path)]

    def clear_cache(self) -> None:
        self._model = None
        self._book_pivot = None
        self._final_rating = None
        self._book_names = []
        self._image_lookup = {}
        self._normalized_title_lookup = {}
        self._artifact_mod_times = {}

    @staticmethod
    def _load_pickle(path: str):
        with open(path, "rb") as file_obj:
            return pickle.load(file_obj)

    def _artifacts_changed(self, artifact_paths: List[str]) -> bool:
        changed = False
        for path in artifact_paths:
            current_mtime = os.path.getmtime(path)
            previous_mtime = self._artifact_mod_times.get(path)
            if previous_mtime is None or previous_mtime != current_mtime:
                changed = True
            self._artifact_mod_times[path] = current_mtime
        return changed

    def _ensure_loaded(self) -> None:
        missing_files = self.missing_artifacts()
        if missing_files:
            raise FileNotFoundError("Recommendation artifacts are missing. Train the model first.")

        artifact_paths = self._required_artifacts()
        should_reload = (
            self._model is None
            or self._book_pivot is None
            or self._final_rating is None
            or self._artifacts_changed(artifact_paths)
        )

        if not should_reload:
            return

        self._model = self._load_pickle(self.recommendation_config.trained_model_path)
        self._book_pivot = self._load_pickle(self.recommendation_config.book_pivot_serialized_objects)
        self._final_rating = self._load_pickle(self.recommendation_config.final_rating_serialized_objects)
        loaded_book_names = self._load_pickle(self.recommendation_config.book_names_serialized_objects)

        self._book_names = list(dict.fromkeys(str(name) for name in loaded_book_names))
        self._normalized_title_lookup = {
            str(title).strip().lower(): str(title) for title in self._book_pivot.index
        }

        deduplicated = self._final_rating.drop_duplicates(subset="title", keep="first")
        self._image_lookup = {}
        for title, image_url in zip(deduplicated["title"], deduplicated["image_url"]):
            normalized_title = str(title)
            if image_url is None:
                self._image_lookup[normalized_title] = None
                continue
            image_value = str(image_url).strip()
            self._image_lookup[normalized_title] = (
                image_value if image_value and image_value.lower() != "nan" else None
            )

    def total_books(self) -> int:
        self._ensure_loaded()
        return len(self._book_names)

    def search_books(self, query: str, limit: int = 8) -> List[str]:
        self._ensure_loaded()

        sanitized_query = (query or "").strip().lower()
        if not sanitized_query:
            return self._book_names[:limit]

        prefix_matches = [
            title for title in self._book_names if title.lower().startswith(sanitized_query)
        ]
        contains_matches = [
            title
            for title in self._book_names
            if sanitized_query in title.lower() and not title.lower().startswith(sanitized_query)
        ]
        return (prefix_matches + contains_matches)[:limit]

    def recommend(self, book_name: str, limit: int = 5) -> Tuple[List[Dict[str, Optional[str]]], str]:
        self._ensure_loaded()

        normalized_input = (book_name or "").strip().lower()
        if not normalized_input:
            raise ValueError("Select a book title to get recommendations.")

        matched_book = self._normalized_title_lookup.get(normalized_input)
        if matched_book is None:
            raise ValueError(f"Book '{book_name}' is not available in the trained recommendation index.")

        book_id = np.where(self._book_pivot.index == matched_book)[0]
        if book_id.size == 0:
            raise ValueError(f"Book '{book_name}' is not available in the trained recommendation index.")

        neighbor_count = min(limit + 1, len(self._book_pivot.index))
        distances, suggestions = self._model.kneighbors(
            self._book_pivot.iloc[book_id[0], :].values.reshape(1, -1),
            n_neighbors=neighbor_count,
        )

        recommendations: List[Dict[str, Optional[str]]] = []
        for suggested_index, distance in zip(suggestions[0], distances[0]):
            suggested_title = str(self._book_pivot.index[suggested_index])
            if suggested_title == matched_book:
                continue

            recommendations.append(
                {
                    "title": suggested_title,
                    "image_url": self._image_lookup.get(suggested_title),
                    "distance": round(float(distance), 4),
                }
            )

            if len(recommendations) >= limit:
                break

        return recommendations, matched_book


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("BOOK_REC_SECRET", "book-recommendation-secret")
engine = RecommendationEngine()


def _template_context(
    selected_book: str = "", recommendations: Optional[List[Dict[str, Optional[str]]]] = None
) -> Dict[str, object]:
    missing_files = engine.missing_artifacts()
    has_artifacts = len(missing_files) == 0

    total_books = 0
    if has_artifacts:
        try:
            total_books = engine.total_books()
        except Exception:
            logging.exception("Could not load total book count")

    return {
        "artifacts_missing": not has_artifacts,
        "missing_artifacts": [path.replace("\\", "/") for path in missing_files],
        "selected_book": selected_book,
        "recommendations": recommendations or [],
        "total_books": total_books,
        "model_name": os.path.basename(engine.recommendation_config.trained_model_path),
    }


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", **_template_context())


@app.route("/recommend", methods=["POST"])
def recommend_books():
    selected_book = request.form.get("book_name", "").strip()

    if not selected_book:
        flash("Select a book title before requesting recommendations.", "error")
        return redirect(url_for("home"))

    if engine.missing_artifacts():
        flash("Model artifacts are missing. Train the pipeline first.", "error")
        return redirect(url_for("home"))

    try:
        recommendations, matched_book = engine.recommend(selected_book, limit=5)
    except ValueError as e:
        flash(str(e), "error")
        return render_template("index.html", **_template_context(selected_book=selected_book))
    except Exception:
        logging.exception("Recommendation request failed")
        flash("Recommendation failed. Check logs and try again.", "error")
        return render_template("index.html", **_template_context(selected_book=selected_book))

    if not recommendations:
        flash("No related titles were found for the selected book.", "error")

    return render_template(
        "index.html",
        **_template_context(selected_book=matched_book, recommendations=recommendations),
    )


@app.route("/train", methods=["POST"])
def train_model():
    try:
        pipeline = TrainingPipeline()
        pipeline.start_training_pipeline()
        engine.clear_cache()
        engine.total_books()
        flash("Training completed successfully.", "success")
    except Exception:
        logging.exception("Training pipeline failed")
        flash("Training failed. Review logs and artifact paths, then retry.", "error")

    return redirect(url_for("home"))


@app.route("/api/books", methods=["GET"])
def book_suggestions():
    query = request.args.get("q", "")
    limit = request.args.get("limit", default=8, type=int)
    limit = max(1, min(limit, 20))

    if engine.missing_artifacts():
        return jsonify({"books": []})

    try:
        return jsonify({"books": engine.search_books(query, limit=limit)})
    except Exception:
        logging.exception("Book suggestion API failed")
        return jsonify({"books": []}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
