"""PMBRS local dashboard package (Phase B — docs/plans/dashboard-milestone-1.md).

Local-first, single-user Streamlit app (Constitution §16). READ-ONLY:
every data read goes through :class:`pmbrs.core.storage.StorageAdapter`;
the app never calls ``save`` / ``derive_from`` / ``mark_module_complete``.
"""
