"""oosc - agent evaluation and reliability engine.

Core claim: everything downstream of ``schema.DomainDef`` is derived from tool
schemas alone (names, param JSON schemas, descriptions, initial DB state).
No benchmark domain code is imported or executed by the world model.
"""

__version__ = "0.1.0"
