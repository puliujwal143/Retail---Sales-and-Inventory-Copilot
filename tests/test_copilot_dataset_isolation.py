"""
test_copilot_dataset_isolation.py
-----------------------------------
Verifies that the AI Copilot pipeline is fully grounded to the active dataset:
- NO_DATA state produces a grounded "no dataset" response
- Copilot entity resolution (stores, products, counts) uses only active dataset facts
- Conversation memory is cleared on dataset switch
- No demo facts appear when NO_DATA or after switching to a new dataset
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dataset_manager import (
    ActiveDatasetManager, create_and_activate_dataset, delete_dataset
)
from src.query_engine import process_query_intent
from src.query_planner import CONVERSATION_MEMORY


def _make_sales(stores, products, date="2026-05-01"):
    rows = []
    for sid, sname in stores:
        for pid, pname, price in products:
            rows.append({
                "sale_id": f"COP_{sid}_{pid}",
                "date": date,
                "store_id": sid, "store_name": sname,
                "product_id": pid, "product_name": pname,
                "quantity": 5,
                "unit_price": float(price),
                "total_revenue": float(price * 5),
            })
    return pd.DataFrame(rows)


# Dataset A: 2 stores, 3 products
DS_A_STORES   = [("SA01", "Alpha Store"), ("SA02", "Beta Store")]
DS_A_PRODUCTS = [("PA01", "Alpha Widget", 100), ("PA02", "Beta Widget", 200), ("PA03", "Gamma Widget", 300)]

# Dataset B: 1 store, 2 products (different names)
DS_B_STORES   = [("SB01", "Delta Store")]
DS_B_PRODUCTS = [("PB01", "Delta Gizmo", 500), ("PB02", "Epsilon Gizmo", 750)]


class TestCopilotDatasetIsolation(unittest.TestCase):

    ID_A = None
    ID_B = None

    def setUp(self):
        # Fresh state for each test if needed
        pass

    @classmethod
    def tearDownClass(cls):
        ActiveDatasetManager.clear_active_dataset()

    # ─── NO_DATA ──────────────────────────────────────────────────────────────
    def test_01_copilot_no_data_response(self):
        """When NO_DATA, Copilot must return a grounded NO_DATA answer, not demo data."""
        ActiveDatasetManager.clear_active_dataset()
        resp = process_query_intent("What is the total revenue?")
        self.assertEqual(resp.get("grounding_state"), "NO_DATA",
                         f"Expected NO_DATA, got: {resp.get('grounding_state')}")
        # Revenue metrics must be empty / zero
        metrics = resp.get("key_metrics", [])
        for m in metrics:
            val = m.get("value", "0")
            # No non-zero revenue should appear
            try:
                self.assertEqual(float(str(val).replace(",", "").replace("₹", "")), 0.0,
                                 f"Non-zero metric in NO_DATA state: {m}")
            except (ValueError, TypeError):
                pass  # non-numeric values (like "N/A") are fine

    def test_02_copilot_no_data_store_count(self):
        """In NO_DATA state, asking store count must not return demo store count."""
        ActiveDatasetManager.clear_active_dataset()
        resp = process_query_intent("How many stores do I have?")
        # Either NO_DATA grounding state or context containing 0 stores
        ctx = resp.get("context_summary", "").lower()
        grounding = resp.get("grounding_state", "")
        is_no_data = (grounding == "NO_DATA") or ("0" in ctx) or ("no dataset" in ctx)
        self.assertTrue(is_no_data, f"NO_DATA state returned store count from another dataset: {resp}")

    # ─── Dataset A isolation ──────────────────────────────────────────────────
    def test_03_copilot_uses_dataset_a_stores(self):
        """With A active, 'how many stores' must reflect A's store count (2)."""
        dfA = _make_sales(DS_A_STORES, DS_A_PRODUCTS)
        create_and_activate_dataset("CopilotTestA", dfA)
        CONVERSATION_MEMORY.clear()
        resp = process_query_intent("How many stores do I have?")
        ctx  = resp.get("context_summary", "")
        # Dataset A has 2 stores
        self.assertIn("2", ctx, f"Expected '2 stores' in context for Dataset A, got: {ctx}")
        # Must NOT mention B's store
        self.assertNotIn("Delta Store", ctx)

    def test_04_copilot_uses_dataset_a_products(self):
        """With A active, product queries must return only A's product names."""
        dfA = _make_sales(DS_A_STORES, DS_A_PRODUCTS)
        create_and_activate_dataset("CopilotTestA", dfA)
        CONVERSATION_MEMORY.clear()
        resp = process_query_intent("List all products")
        ctx  = resp.get("context_summary", "")
        # At least one A product should appear
        a_names_in_ctx = [name for name in ["Alpha Widget", "Beta Widget", "Gamma Widget"] if name in ctx]
        self.assertGreater(len(a_names_in_ctx), 0, f"No Dataset A products found in context: {ctx}")
        # B products must not appear
        self.assertNotIn("Delta Gizmo", ctx)
        self.assertNotIn("Epsilon Gizmo", ctx)

    # ─── Dataset B isolation ──────────────────────────────────────────────────
    def test_05_copilot_uses_dataset_b_stores(self):
        """With B active, 'how many stores' must reflect B's store count (1)."""
        dfB = _make_sales(DS_B_STORES, DS_B_PRODUCTS)
        create_and_activate_dataset("CopilotTestB", dfB)
        CONVERSATION_MEMORY.clear()
        resp = process_query_intent("How many stores do I have?")
        ctx  = resp.get("context_summary", "")
        self.assertIn("1", ctx, f"Expected '1 store' in context for Dataset B, got: {ctx}")
        self.assertNotIn("Alpha Store", ctx)
        self.assertNotIn("Beta Store", ctx)

    def test_06_copilot_uses_dataset_b_products(self):
        """With B active, product queries must return only B's product names."""
        dfB = _make_sales(DS_B_STORES, DS_B_PRODUCTS)
        create_and_activate_dataset("CopilotTestB", dfB)
        CONVERSATION_MEMORY.clear()
        resp = process_query_intent("List all products")
        ctx  = resp.get("context_summary", "")
        b_names_in_ctx = [n for n in ["Delta Gizmo", "Epsilon Gizmo"] if n in ctx]
        self.assertGreater(len(b_names_in_ctx), 0, f"No Dataset B products found in context: {ctx}")
        self.assertNotIn("Alpha Widget", ctx)

    # ─── Context cleared on switch ────────────────────────────────────────────
    def test_07_conversation_memory_cleared_on_switch(self):
        """Switching / replacing datasets must clear the conversation memory."""
        dfA = _make_sales(DS_A_STORES, DS_A_PRODUCTS)
        create_and_activate_dataset("CopilotTestA", dfA)
        CONVERSATION_MEMORY["last_store"] = "Alpha Store"
        CONVERSATION_MEMORY["last_product"] = "Alpha Widget"

        # Uploading B replaces A and triggers invalidation callback that clears CONVERSATION_MEMORY
        dfB = _make_sales(DS_B_STORES, DS_B_PRODUCTS)
        create_and_activate_dataset("CopilotTestB", dfB)

        self.assertIsNone(CONVERSATION_MEMORY.get("last_store"),
                          "Conversation memory 'last_store' was not cleared after dataset switch")
        self.assertIsNone(CONVERSATION_MEMORY.get("last_product"),
                          "Conversation memory 'last_product' was not cleared after dataset switch")

    # ─── A→B switch erases A context ─────────────────────────────────────────
    def test_08_copilot_context_not_persisted_across_switch(self):
        """After replacing A with B, queries about stores must return B's data only."""
        dfA = _make_sales(DS_A_STORES, DS_A_PRODUCTS)
        create_and_activate_dataset("CopilotTestA", dfA)
        CONVERSATION_MEMORY.clear()

        # Ask about stores while on A
        resp_a = process_query_intent("How many stores do I have?")
        ctx_a  = resp_a.get("context_summary", "")
        self.assertIn("2", ctx_a)

        # Replace with B
        dfB = _make_sales(DS_B_STORES, DS_B_PRODUCTS)
        create_and_activate_dataset("CopilotTestB", dfB)
        CONVERSATION_MEMORY.clear()

        # Same question must now reflect B's data
        resp_b = process_query_intent("How many stores do I have?")
        ctx_b  = resp_b.get("context_summary", "")
        self.assertIn("1", ctx_b, f"After switch to B, expected '1 store', got: {ctx_b}")
        self.assertNotIn("Alpha Store", ctx_b,
                         "A's 'Alpha Store' leaked into B's Copilot context after switching")


if __name__ == "__main__":
    unittest.main()
