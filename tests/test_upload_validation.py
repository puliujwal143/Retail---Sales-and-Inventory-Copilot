import unittest
import os
import io
import pandas as pd
from fastapi.testclient import TestClient
from app import app
from src.dataset_manager import ActiveDatasetManager

class TestUploadValidation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Create minimal CSV data in memory
        self.sales_csv = "sale_id,store_id,product_id,date,quantity,unit_price,total_revenue\nS1,STR001,PRD001,2026-08-01,5,100,500\n"
        self.inv_csv = "store_id,product_id,current_stock,reorder_point,safety_stock,last_restock_date\nSTR001,PRD001,50,10,5,2026-08-01\n"
        self.prod_csv = "product_id,product_name,category,unit_price,cost_price\nPRD001,Test Product,Groceries,100,60\n"
        self.stores_csv = "store_id,store_name,location\nSTR001,Test Store,Downtown\n"

    def tearDown(self):
        # Reset to Demo
        self.client.post("/api/datasets/reset")

    def test_01_empty_dataset_name_rejected(self):
        """TEST 1: Dataset Name empty -> FAIL 'Dataset name is required.'"""
        files = {"file": ("test_sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv")}
        data = {"dataset_name": "   "}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Dataset name is required.", response.json()["detail"])

    def test_02_single_file_valid_success(self):
        """TEST 2: Dataset Name entered + Single File -> SUCCESS"""
        files = {"file": ("test_sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv")}
        data = {"dataset_name": "Valid Single File DS"}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json["success"])
        self.assertEqual(res_json["dataset"]["dataset_name"], "Valid Single File DS")

    def test_03_4csv_only_sales_rejected(self):
        """TEST 3: Dataset Name entered + 4 CSV mode + Only Sales -> FAIL (Inventory, Products, Stores missing)"""
        files = {
            "sales_file": ("sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv")
        }
        data = {"dataset_name": "Incomplete 4 CSV"}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Inventory CSV is required.", response.json()["detail"])

    def test_04_4csv_stores_missing_rejected(self):
        """TEST 4: Dataset Name entered + 4 CSV mode + Sales + Inventory + Products (Stores missing) -> FAIL"""
        files = {
            "sales_file": ("sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv"),
            "inventory_file": ("inventory.csv", io.BytesIO(self.inv_csv.encode("utf-8")), "text/csv"),
            "products_file": ("products.csv", io.BytesIO(self.prod_csv.encode("utf-8")), "text/csv")
        }
        data = {"dataset_name": "Missing Stores DS"}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Stores CSV is required.", response.json()["detail"])

    def test_05_4csv_all_four_files_success(self):
        """TEST 5: Dataset Name entered + 4 CSV mode + All 4 CSVs -> SUCCESS"""
        files = {
            "sales_file": ("sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv"),
            "inventory_file": ("inventory.csv", io.BytesIO(self.inv_csv.encode("utf-8")), "text/csv"),
            "products_file": ("products.csv", io.BytesIO(self.prod_csv.encode("utf-8")), "text/csv"),
            "stores_file": ("stores.csv", io.BytesIO(self.stores_csv.encode("utf-8")), "text/csv")
        }
        data = {"dataset_name": "Complete 4 CSV DS"}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json["success"])
        self.assertEqual(res_json["dataset"]["dataset_name"], "Complete 4 CSV DS")

    def test_06_single_file_mode_no_file_rejected(self):
        """TEST 6: Dataset Name entered + No files uploaded -> FAIL"""
        data = {"dataset_name": "No File DS"}
        response = self.client.post("/api/datasets/upload", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Sales CSV is required.", response.json()["detail"])

    def test_07_invalid_file_extension_rejected(self):
        """Invalid file extension rejected"""
        files = {"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")}
        data = {"dataset_name": "Invalid File DS"}
        response = self.client.post("/api/datasets/upload", data=data, files=files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file type", response.json()["detail"])

    def test_08_validate_endpoint_dry_run_multi_missing(self):
        """Dry-run validation endpoint correctly flags missing files in 4 CSV mode"""
        files = {
            "sales_file": ("sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv")
        }
        response = self.client.post("/api/datasets/validate", files=files)
        self.assertEqual(response.status_code, 200)
        val = response.json()
        self.assertFalse(val["is_valid"])
        self.assertTrue(any("Inventory CSV is required." in e for e in val["errors"]))
        self.assertTrue(any("Products CSV is required." in e for e in val["errors"]))
        self.assertTrue(any("Stores CSV is required." in e for e in val["errors"]))

    def test_09_validate_endpoint_dry_run_multi_complete(self):
        """Dry-run validation endpoint passes when all 4 CSVs are supplied"""
        files = {
            "sales_file": ("sales.csv", io.BytesIO(self.sales_csv.encode("utf-8")), "text/csv"),
            "inventory_file": ("inventory.csv", io.BytesIO(self.inv_csv.encode("utf-8")), "text/csv"),
            "products_file": ("products.csv", io.BytesIO(self.prod_csv.encode("utf-8")), "text/csv"),
            "stores_file": ("stores.csv", io.BytesIO(self.stores_csv.encode("utf-8")), "text/csv")
        }
        response = self.client.post("/api/datasets/validate", files=files)
        self.assertEqual(response.status_code, 200)
        val = response.json()
        self.assertTrue(val["is_valid"])
        self.assertEqual(val["summary"]["sales_count"], 1)

if __name__ == "__main__":
    unittest.main()
