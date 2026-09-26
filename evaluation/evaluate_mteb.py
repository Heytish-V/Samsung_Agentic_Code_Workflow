import json

import mteb
from mteb.models.abs_encoder import AbsEncoder
from mteb.models.model_meta import ModelMeta
from sentence_transformers import SentenceTransformer


class PrePostPipelineEncoder(AbsEncoder):
    def __init__(self, model_name="BAAI/bge-small-en-v1.5"):
        super().__init__()

        print(f"Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)

        self.model_meta = ModelMeta(
            loader=SentenceTransformer,
            loader_kwargs={"model_name_or_path": model_name},
            name="BAAI/bge-small-en-v1.5",
            revision="1.0",
            release_date="2026-09-26",
            languages=["eng-Latn"],
            n_parameters=33_000_000,
            memory_usage_mb=133,
            max_tokens=512,
            embed_dim=384,
            license="mit",
            open_weights=True,
            public_training_code=None,
            public_training_data=None,
            framework=["Sentence Transformers"],
            similarity_fn_name="cosine",
            use_instructions=False,
            training_datasets=None,
        )

    def _text(self, item):
        if isinstance(item, str):
            return item

        if isinstance(item, dict):
            for key in ["text", "code", "content", "description"]:
                value = item.get(key)
                if isinstance(value, str):
                    return value

            return json.dumps(item)

        return str(item)

    def encode(self, texts, prompt_type=None, **kwargs):
        formatted = [
            f"passage: {self._text(text).strip()}"
            for text in texts
        ]

        return self.model.encode(
            formatted,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def encode_queries(self, queries, prompt_type=None, **kwargs):
        formatted = [
            f"query: {self._text(query).strip()}"
            for query in queries
        ]

        return self.model.encode(
            formatted,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )


def main():
    print("[1/3] Initializing MTEB encoder on CPU...")

    encoder = PrePostPipelineEncoder()

    print("[2/3] Loading AppsRetrieval task...")

    task = mteb.get_task("AppsRetrieval")

    print("[3/3] Running MTEB AppsRetrieval benchmark...")
    print("This may take some time on the first run.")

    evaluation = mteb.MTEB(tasks=[task])

    result = evaluation.run(
        encoder,
        output_folder="evaluation/results",
        encode_kwargs={"batch_size": 64},
    )

    # MTEB 2.21.x returns a list of task results
    task_result = result[0]

    output_filename = "appsretrieval_results.json"

    with open(
        output_filename,
        "w",
        encoding="utf-8",
    ) as f:
        if hasattr(task_result, "to_dict"):
            json.dump(task_result.to_dict(), f, indent=2)
        else:
            json.dump(task_result, f, indent=2, default=str)

    print()
    print("=" * 60)
    print("[SUCCESS] MTEB evaluation completed!")
    print(f"[SUCCESS] Generated: {output_filename}")
    print("=" * 60)


if __name__ == "__main__":
    main()