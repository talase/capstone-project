from __future__ import annotations

import unittest
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.files as files_routes


@dataclass
class FakeResponse:
    data: list[dict[str, object]]


class FakeQuery:
    def __init__(
        self,
        calls: list[tuple[object, ...]],
        table_name: str,
        responses: dict[tuple[object, ...], list[dict[str, object]]],
    ):
        self.calls = calls
        self.table_name = table_name
        self.responses = responses
        self.operation = ""
        self.column = ""
        self.value: object = None

    def select(self, columns: str):
        self.operation = "select"
        self.calls.append(("select", self.table_name, columns))
        return self

    def delete(self):
        self.operation = "delete"
        self.calls.append(("delete", self.table_name))
        return self

    def eq(self, column: str, value: object):
        self.column = column
        self.value = value
        self.calls.append(("eq", self.table_name, column, value))
        return self

    def limit(self, count: int):
        self.calls.append(("limit", self.table_name, count))
        return self

    def execute(self):
        key = (self.operation, self.table_name, self.column, self.value)
        self.calls.append(("execute", *key))
        result = self.responses.get(key, [])
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


class FakeBucket:
    def __init__(self, calls: list[tuple[object, ...]]):
        self.calls = calls

    def remove(self, paths: list[str]):
        self.calls.append(("storage_remove", paths))
        return []


class FakeStorage:
    def __init__(self, calls: list[tuple[object, ...]]):
        self.calls = calls

    def from_(self, bucket_name: str):
        self.calls.append(("storage_bucket", bucket_name))
        return FakeBucket(self.calls)


class FakeSupabase:
    def __init__(
        self,
        responses: dict[tuple[object, ...], list[dict[str, object]]],
    ):
        self.calls: list[tuple[object, ...]] = []
        self.responses = responses
        self.storage = FakeStorage(self.calls)

    def table(self, table_name: str):
        self.calls.append(("table", table_name))
        return FakeQuery(self.calls, table_name, self.responses)


def make_client(fake_supabase: FakeSupabase) -> TestClient:
    files_routes.get_supabase_service_client = lambda: fake_supabase
    files_routes.get_storage_bucket_name = lambda: "user-files"
    app = FastAPI()
    app.include_router(files_routes.router)
    return TestClient(app)


def test_delete_removes_rag_rows_file_row_then_storage() -> None:
    storage_path = "dashboard_uploads/20260615T120000Z_test.pdf"
    file_id = "925121b1-7697-4cf4-b410-65e9855465f5"
    fake = FakeSupabase(
        {
            ("select", "files", "storage_path", storage_path): [{"id": file_id}],
            (
                "delete",
                "file_rag_documents",
                "metadata->>storage_path",
                storage_path,
            ): [{"id": "chunk-1"}],
            (
                "delete",
                "file_rag_documents",
                "metadata->>file_id",
                file_id,
            ): [{"id": "chunk-1"}, {"id": "chunk-2"}],
            ("delete", "files", "storage_path", storage_path): [{"id": file_id}],
        }
    )

    response = make_client(fake).delete(
        "/files/dashboard-upload",
        params={"storage_path": storage_path},
    )

    assert response.status_code == 200
    assert response.json()["deleted_file_rows"] == 1
    assert response.json()["deleted_rag_documents"] == 2
    assert fake.calls[-1] == ("storage_remove", [storage_path])

    file_delete_index = fake.calls.index(
        ("execute", "delete", "files", "storage_path", storage_path)
    )
    storage_delete_index = fake.calls.index(("storage_remove", [storage_path]))
    assert file_delete_index < storage_delete_index


def test_delete_uses_storage_path_when_files_row_is_missing() -> None:
    storage_path = "dashboard_uploads/orphan.txt"
    fake = FakeSupabase(
        {
            ("select", "files", "storage_path", storage_path): [],
            (
                "delete",
                "file_rag_documents",
                "metadata->>storage_path",
                storage_path,
            ): [{"id": "chunk-1"}],
            ("delete", "files", "storage_path", storage_path): [],
        }
    )

    response = make_client(fake).delete(
        "/files/dashboard-upload",
        params={"storage_path": storage_path},
    )

    assert response.status_code == 200
    assert response.json()["file_id"] is None
    assert response.json()["deleted_rag_documents"] == 1
    assert not any(
        call[:3] == ("eq", "file_rag_documents", "metadata->>file_id")
        for call in fake.calls
    )


def test_delete_rejects_paths_outside_dashboard_uploads() -> None:
    fake = FakeSupabase({})
    response = make_client(fake).delete(
        "/files/dashboard-upload",
        params={"storage_path": "other_folder/private.pdf"},
    )

    assert response.status_code == 400
    assert fake.calls == []


def test_database_failure_does_not_remove_storage() -> None:
    storage_path = "dashboard_uploads/retryable.pdf"
    fake = FakeSupabase(
        {
            ("select", "files", "storage_path", storage_path): [{"id": "file-1"}],
            (
                "delete",
                "file_rag_documents",
                "metadata->>storage_path",
                storage_path,
            ): RuntimeError("database unavailable"),
        }
    )

    response = make_client(fake).delete(
        "/files/dashboard-upload",
        params={"storage_path": storage_path},
    )

    assert response.status_code == 502
    assert not any(call[0] == "storage_remove" for call in fake.calls)


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    return unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for test in (
            test_delete_removes_rag_rows_file_row_then_storage,
            test_delete_uses_storage_path_when_files_row_is_missing,
            test_delete_rejects_paths_outside_dashboard_uploads,
            test_database_failure_does_not_remove_storage,
        )
    )
