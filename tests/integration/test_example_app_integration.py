"""Integration tests for FastAPI example application."""

import uuid

from fastapi.testclient import TestClient

from examples.fastapi_integration import CreateDemoSchema, UpdateDemoSchema, app


class TestExampleAppIntegration:
    """Test FastAPI example application integration scenarios."""

    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["redis_connected"] is True
            assert "timestamp" in data

    def test_root_redirect(self):
        """Test root endpoint redirects to docs."""
        with TestClient(app) as client:
            response = client.get("/", follow_redirects=False)
            assert response.status_code == 307
            assert response.headers["location"] == "/docs"

    def test_redis_dependency_injection_crud(self):
        """Test Redis dependency injection CRUD operations."""
        with TestClient(app) as client:
            key = "test_dependency_key"
            value = "test_dependency_value"

            # Create
            response = client.post(f"/depends/{key}", params={"value": value})
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == key
            assert data["value"] == value

            # Read
            response = client.get(f"/depends/{key}")
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == key
            assert data["value"] == value

            # Check exists
            response = client.get(f"/depends/{key}/exists")
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == key
            assert data["exists"] is True

            # Delete
            response = client.delete(f"/depends/{key}")
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == key

            # Verify deletion
            response = client.get(f"/depends/{key}")
            assert response.status_code == 404

    def test_redis_dependency_nonexistent_key(self):
        """Test Redis dependency with non-existent key."""
        with TestClient(app) as client:
            response = client.get("/depends/nonexistent_key")
            assert response.status_code == 404
            data = response.json()
            assert "not found in cache" in data["detail"]

    def test_redis_dependency_delete_nonexistent(self):
        """Test Redis dependency delete non-existent key."""
        with TestClient(app) as client:
            response = client.delete("/depends/nonexistent_key")
            assert response.status_code == 404
            data = response.json()
            assert "not found in cache" in data["detail"]

    def test_demo_repository_crud_operations(self):
        """Test demo repository CRUD operations through API."""
        with TestClient(app) as client:
            # Create
            create_data = CreateDemoSchema(field1="test_field1", field2="test_field2")
            response = client.post("/repo/", json=create_data.model_dump())
            assert response.status_code == 201
            created_demo = response.json()
            demo_id = created_demo["key"]
            assert created_demo["field1"] == "test_field1"
            assert created_demo["field2"] == "test_field2"

            # Read
            response = client.get(f"/repo/{demo_id}")
            assert response.status_code == 200
            demo = response.json()
            assert demo["key"] == demo_id
            assert demo["field1"] == "test_field1"
            assert demo["field2"] == "test_field2"

            # Update
            update_data = UpdateDemoSchema(field1="updated_field1")
            response = client.put(f"/repo/{demo_id}", json=update_data.model_dump(exclude_unset=True))
            assert response.status_code == 200
            updated_demo = response.json()
            assert updated_demo["key"] == demo_id
            assert updated_demo["field1"] == "updated_field1"
            assert updated_demo["field2"] == "test_field2"  # unchanged

            # Check exists
            response = client.get(f"/repo/{demo_id}/exists")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == demo_id
            assert data["exists"] is True

            # Delete
            response = client.delete(f"/repo/{demo_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == demo_id

            # Verify deletion
            response = client.get(f"/repo/{demo_id}")
            assert response.status_code == 404

    def test_demo_repository_list_operations(self):
        """Test demo repository list operations."""
        with TestClient(app) as client:
            # Create multiple records
            demo_ids = []
            for i in range(3):
                create_data = CreateDemoSchema(field1=f"test_field1_{i}", field2=f"test_field2_{i}")
                response = client.post("/repo/", json=create_data.model_dump())
                assert response.status_code == 201
                demo = response.json()
                demo_ids.append(demo["key"])

            # List all records
            response = client.get("/repo/")
            assert response.status_code == 200
            demos = response.json()
            assert len(demos) >= 3

            # Verify all created records are in the list
            demo_keys = [demo["key"] for demo in demos]
            for demo_id in demo_ids:
                assert demo_id in demo_keys

    def test_demo_repository_list_with_limit(self):
        """Test demo repository list with limit."""
        with TestClient(app) as client:
            # Create multiple records
            for i in range(5):
                create_data = CreateDemoSchema(field1=f"test_field1_{i}", field2=f"test_field2_{i}")
                response = client.post("/repo/", json=create_data.model_dump())
                assert response.status_code == 201

            # List with limit
            response = client.get("/repo/?limit=3")
            assert response.status_code == 200
            demos = response.json()
            assert len(demos) <= 3

    def test_demo_repository_nonexistent_operations(self):
        """Test demo repository operations with non-existent records."""
        with TestClient(app) as client:
            fake_id = str(uuid.uuid4())

            # Get non-existent
            response = client.get(f"/repo/{fake_id}")
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]

            # Update non-existent
            update_data = UpdateDemoSchema(field1="updated")
            response = client.put(f"/repo/{fake_id}", json=update_data.model_dump(exclude_unset=True))
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]

            # Delete non-existent
            response = client.delete(f"/repo/{fake_id}")
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]

            # Check exists for non-existent
            response = client.get(f"/repo/{fake_id}/exists")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == fake_id
            assert data["exists"] is False

    def test_demo_repository_validation_errors(self):
        """Test demo repository validation errors."""
        with TestClient(app) as client:
            # Invalid create data (missing required fields)
            response = client.post("/repo/", json={"field1": "test"})  # missing field2
            assert response.status_code == 422

            # Invalid update data (wrong types)
            demo_id = str(uuid.uuid4())
            response = client.put(f"/repo/{demo_id}", json={"field1": 123})  # wrong type
            assert response.status_code == 422

    def test_demo_repository_partial_update(self):
        """Test demo repository partial update."""
        with TestClient(app) as client:
            # Create record
            create_data = CreateDemoSchema(field1="original_field1", field2="original_field2")
            response = client.post("/repo/", json=create_data.model_dump())
            assert response.status_code == 201
            demo_id = response.json()["key"]

            # Partial update (only field1)
            update_data = UpdateDemoSchema(field1="updated_field1")
            response = client.put(f"/repo/{demo_id}", json=update_data.model_dump(exclude_unset=True))
            assert response.status_code == 200
            updated_demo = response.json()
            assert updated_demo["field1"] == "updated_field1"
            assert updated_demo["field2"] == "original_field2"  # unchanged

            # Partial update (only field2)
            update_data = UpdateDemoSchema(field2="updated_field2")
            response = client.put(f"/repo/{demo_id}", json=update_data.model_dump(exclude_unset=True))
            assert response.status_code == 200
            updated_demo = response.json()
            assert updated_demo["field1"] == "updated_field1"  # unchanged
            assert updated_demo["field2"] == "updated_field2"

    def test_demo_repository_empty_list(self):
        """Test demo repository list when no records exist."""
        with TestClient(app) as client:
            response = client.get("/repo/")
            assert response.status_code == 200
            demos = response.json()
            assert demos == []
