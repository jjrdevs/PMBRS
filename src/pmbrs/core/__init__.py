"""PMBRS core infrastructure — shared artifacts and storage (not module logic).

Per ``docs/module-contracts.md``: ``core/`` holds the ``StorageAdapter`` and
artifact primitives that every subsystem module (ingestion, temporal,
features, representation, experimentation, evaluation) imports. Consumers
never open store files directly.
"""
