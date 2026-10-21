# Copyright 2026 EOAP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import inspect
import json
import unittest
from typing import get_args

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request

import http_apis_problems_detail as registry
import http_apis_problems_detail.fastapi as fastapi_registry
from http_apis_problems_detail.fastapi import ProblemRegistryException


class ProblemResponsesTest(unittest.TestCase):
    def test_route_openapi_includes_all_problem_schemas(self) -> None:
        app = FastAPI()

        @app.get("/sample", responses=fastapi_registry.PROBLEM_RESPONSES)
        def sample() -> str:
            return "ok"

        document = app.openapi()
        responses = document["paths"]["/sample"]["get"]["responses"]
        self.assertEqual(set(responses["200"]["content"]), {"application/json"})
        expected_models = set(get_args(fastapi_registry.ProblemType))
        documented_names = []
        for status_code, response in responses.items():
            if status_code == "200":
                continue
            self.assertEqual(set(response["content"]), {"application/problem+json"})
            schema = response["content"]["application/problem+json"]["schema"]
            for alternative in schema.get("anyOf", [schema]):
                documented_names.append(alternative["title"])
                self.assertEqual(alternative["properties"]["status"]["const"], int(status_code))
        self.assertCountEqual(documented_names, [model.__name__ for model in expected_models])

        for model_type in expected_models:
            with self.subTest(model=model_type.__name__):
                status_code = str(model_type.model_fields["status"].default)
                schema = responses[status_code]["content"]["application/problem+json"]["schema"]
                alternatives = schema.get("anyOf", [schema])
                model_schema = next(
                    item for item in alternatives if item["title"] == model_type.__name__
                )
                expected_schema = model_type.model_json_schema(mode="serialization")
                definitions = expected_schema.pop("$defs")
                error_schema = expected_schema["properties"]["errors"]["anyOf"][0]
                error_schema["items"] = definitions["ErrorDetail"]
                # FastAPI omits null-valued metadata when serializing OpenAPI.
                self.assertEqual(model_schema, jsonable_encoder(expected_schema, exclude_none=True))
                self.assertNotIn('"$ref"', json.dumps(model_schema))
                self.assertNotIn('"$defs"', json.dumps(model_schema))

    def test_selected_response_preserves_default_validation_response(self) -> None:
        app = FastAPI()

        @app.get("/sample/{resource_id}", responses={404: fastapi_registry.PROBLEM_RESPONSES[404]})
        def sample(resource_id: int) -> int:
            return resource_id

        responses = app.openapi()["paths"]["/sample/{resource_id}"]["get"]["responses"]
        self.assertEqual(set(responses["404"]["content"]), {"application/problem+json"})
        self.assertEqual(set(responses["422"]["content"]), {"application/json"})
        self.assertEqual(set(responses["200"]["content"]), {"application/json"})
        problem_schema = responses["404"]["content"]["application/problem+json"]["schema"]
        self.assertNotIn('"$ref"', json.dumps(problem_schema))
        self.assertNotIn('"$defs"', json.dumps(problem_schema))


class ProblemRegistryExceptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.request = Request(
            {
                "type": "http",
                "scheme": "https",
                "server": ("example.com", 443),
                "path": "/instances/sample",
                "headers": [],
            }
        )
        self.problem = registry.MissingRequestParameter(
            instance="/instances/previous",
            code="400-03",
            errors=[
                registry.ErrorDetail(
                    detail="The query parameter limit is required.",
                    parameter="limit",
                )
            ],
        )

        self.exception = ProblemRegistryException(request=self.request, problem=self.problem)

    def test_is_an_http_exception_with_the_problem_status(self) -> None:
        self.assertIsInstance(self.exception, HTTPException)
        self.assertEqual(self.exception.status_code, self.problem.status)

    def test_serializes_the_problem_as_the_exception_detail(self) -> None:
        self.assertIsInstance(self.exception.detail, str)
        self.assertEqual(
            json.loads(self.exception.detail),
            self.problem.model_dump(mode="json", exclude_none=True),
        )

    def test_request_url_replaces_the_existing_problem_instance(self) -> None:
        self.assertEqual(self.problem.instance, "https://example.com/instances/sample")
        self.assertEqual(
            json.loads(self.exception.detail)["instance"], "https://example.com/instances/sample"
        )

    def test_request_url_sets_an_unset_problem_instance(self) -> None:
        exception = ProblemRegistryException(request=self.request, problem=registry.BadRequest())

        self.assertEqual(
            json.loads(exception.detail)["instance"], "https://example.com/instances/sample"
        )

    def test_uses_the_problem_json_content_type(self) -> None:
        self.assertEqual(
            self.exception.headers,
            {"Content-Type": "application/problem+json"},
        )

    def test_handler_returns_problem_json_with_custom_headers(self) -> None:
        exception = fastapi_registry.MissingRequestParameterException(
            request=self.request, headers={"X-Request-ID": "abc123"}
        )
        response = asyncio.run(
            fastapi_registry.problem_registry_exception_handler(self.request, exception)
        )

        self.assertEqual(
            json.loads(bytes(response.body))["instance"], "https://example.com/instances/sample"
        )
        self.assertEqual(response.status_code, exception.status_code)
        self.assertEqual(bytes(response.body).decode(), exception.detail)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(response.headers["X-Request-ID"], "abc123")


class DeclaredProblemRegistryExceptionsTest(unittest.TestCase):
    exception_types = (
        fastapi_registry.AlreadyExistsException,
        fastapi_registry.BadRequestException,
        fastapi_registry.BusinessRuleViolationException,
        fastapi_registry.ConflictException,
        fastapi_registry.FailedDependencyException,
        fastapi_registry.ForbiddenException,
        fastapi_registry.GoneException,
        fastapi_registry.InsufficientStorageException,
        fastapi_registry.InvalidBodyPropertyFormatException,
        fastapi_registry.InvalidBodyPropertyValueException,
        fastapi_registry.InvalidParametersException,
        fastapi_registry.InvalidRequestHeaderFormatException,
        fastapi_registry.InvalidRequestParameterFormatException,
        fastapi_registry.InvalidRequestParameterValueException,
        fastapi_registry.InvalidStateTransitionException,
        fastapi_registry.LicenseCancelledException,
        fastapi_registry.LicenseExpiredException,
        fastapi_registry.MissingBodyPropertyException,
        fastapi_registry.MissingRequestHeaderException,
        fastapi_registry.MissingRequestParameterException,
        fastapi_registry.MethodNotAllowedException,
        fastapi_registry.NotAcceptableException,
        fastapi_registry.NotFoundException,
        fastapi_registry.NotImplementedException,
        fastapi_registry.RequestTimeoutException,
        fastapi_registry.ServerErrorException,
        fastapi_registry.ServiceUnavailableException,
        fastapi_registry.UnauthorizedException,
        fastapi_registry.UnavailableForLegalReasonsException,
        fastapi_registry.UnprocessableContentException,
        fastapi_registry.ValidationErrorException,
    )

    def setUp(self) -> None:
        self.request = Request(
            {
                "type": "http",
                "scheme": "https",
                "server": ("example.com", 443),
                "path": "/instances/sample",
                "headers": [],
            }
        )

    def test_each_declared_exception_reflects_its_related_problem_model(self) -> None:
        declared_types = {
            exception_type
            for _, exception_type in inspect.getmembers(fastapi_registry, inspect.isclass)
            if exception_type.__module__ == fastapi_registry.__name__
            and exception_type is not ProblemRegistryException
            and issubclass(exception_type, ProblemRegistryException)
            and exception_type.__name__.endswith("Exception")
        }
        self.assertEqual(set(self.exception_types), declared_types)

        for exception_type in self.exception_types:
            with self.subTest(exception=exception_type.__name__):
                problem_model_name = exception_type.__name__.removesuffix("Exception")
                problem_model_type = getattr(registry, problem_model_name)

                problem = problem_model_type(instance="https://example.com/instances/sample")
                exception = exception_type(request=self.request)

                self.assertIsInstance(exception, HTTPException)
                self.assertEqual(exception.status_code, problem.status)
                self.assertEqual(
                    json.loads(exception.detail),
                    problem.model_dump(mode="json", exclude_none=True),
                )
                self.assertEqual(
                    exception.headers,
                    {"Content-Type": "application/problem+json"},
                )

    def test_each_thrown_exception_uses_the_request_url(self) -> None:
        for exception_type in self.exception_types:
            with self.subTest(exception=exception_type.__name__):
                with self.assertRaises(exception_type) as raised:
                    raise exception_type(request=self.request)

                self.assertEqual(
                    json.loads(raised.exception.detail)["instance"],
                    "https://example.com/instances/sample",
                )

    def test_each_declared_exception_preserves_the_request_url_without_query(self) -> None:
        cases = (
            ("https", 443, "/", b"", "https://example.com/"),
            (
                "https",
                8443,
                "/collections/sample/items/",
                b"limit=10&offset=20",
                "https://example.com:8443/collections/sample/items/",
            ),
            (
                "http",
                80,
                "/search",
                b"q=hello%20world&tag=a&tag=b",
                "http://example.com/search",
            ),
        )
        for scheme, port, path, query_string, expected_instance in cases:
            request = Request(
                {
                    "type": "http",
                    "headers": [],
                    "scheme": scheme,
                    "server": ("example.com", port),
                    "path": path,
                    "query_string": query_string,
                }
            )
            for exception_type in self.exception_types:
                with self.subTest(exception=exception_type.__name__, url=expected_instance):
                    exception = exception_type(request=request)

                    self.assertEqual(json.loads(exception.detail)["instance"], expected_instance)

    def test_each_declared_exception_sets_a_single_error(self) -> None:
        error = registry.ErrorDetail(
            detail="The supplied value is invalid.",
            parameter="limit",
        )
        expected_errors = [error.model_dump(mode="json", exclude_none=True)]

        for exception_type in self.exception_types:
            with self.subTest(exception=exception_type.__name__):
                exception = exception_type(request=self.request, errors=error)
                detail = json.loads(exception.detail)

                self.assertEqual(detail["instance"], "https://example.com/instances/sample")
                self.assertEqual(detail["errors"], expected_errors)

    def test_each_declared_exception_sets_multiple_errors(self) -> None:
        errors = [
            registry.ErrorDetail(
                detail="The supplied value is invalid.",
                parameter="limit",
            ),
            registry.ErrorDetail(
                detail="The supplied header is invalid.",
                header="X-Request-ID",
            ),
        ]
        expected_errors = [error.model_dump(mode="json", exclude_none=True) for error in errors]

        for exception_type in self.exception_types:
            with self.subTest(exception=exception_type.__name__):
                exception = exception_type(request=self.request, errors=errors)
                detail = json.loads(exception.detail)

                self.assertEqual(detail["instance"], "https://example.com/instances/sample")
                self.assertEqual(detail["errors"], expected_errors)

    def test_each_declared_exception_merges_custom_headers(self) -> None:
        headers = {
            "X-Request-ID": "abc123",
            "Content-Type": "text/plain",
        }

        for exception_type in self.exception_types:
            with self.subTest(exception=exception_type.__name__):
                exception = exception_type(request=self.request, headers=headers)

                self.assertEqual(
                    json.loads(exception.detail)["instance"], "https://example.com/instances/sample"
                )

                self.assertEqual(
                    exception.headers,
                    {
                        "X-Request-ID": "abc123",
                        "Content-Type": "application/problem+json",
                    },
                )
                self.assertEqual(
                    headers,
                    {
                        "X-Request-ID": "abc123",
                        "Content-Type": "text/plain",
                    },
                )


if __name__ == "__main__":
    unittest.main()
