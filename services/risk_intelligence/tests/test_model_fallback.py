import unittest
from unittest.mock import patch

from app import mlflow_utils


class ProjectModelFallbackTests(unittest.TestCase):
    def setUp(self):
        self.original_model = mlflow_utils._cached_model
        self.original_version = mlflow_utils._cached_version
        mlflow_utils._cached_model = None
        mlflow_utils._cached_version = None

    def tearDown(self):
        mlflow_utils._cached_model = self.original_model
        mlflow_utils._cached_version = self.original_version

    @patch("app.mlflow_utils.joblib.load", return_value=object())
    @patch("app.mlflow_utils.Path.is_file", return_value=True)
    def test_missing_registry_falls_back_to_archived_project_model(self, _exists, load_model):
        model, version = mlflow_utils.get_or_train_model()

        self.assertIs(model, load_model.return_value)
        self.assertEqual(version, "synthetic:project-v1")
        self.assertTrue(str(load_model.call_args.args[0]).endswith("Synthetic_Model.pkl"))


if __name__ == "__main__":
    unittest.main()
