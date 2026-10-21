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

"""Expose registry problems as FastAPI exceptions and HTTP responses."""

from __future__ import annotations

from typing import TYPE_CHECKING, get_args

from fastapi import HTTPException
from fastapi.responses import Response

from . import (
    AlreadyExists,
    BadRequest,
    BusinessRuleViolation,
    Conflict,
    ErrorDetail,
    FailedDependency,
    Forbidden,
    Gone,
    InsufficientStorage,
    InvalidBodyPropertyFormat,
    InvalidBodyPropertyValue,
    InvalidParameters,
    InvalidRequestHeaderFormat,
    InvalidRequestParameterFormat,
    InvalidRequestParameterValue,
    InvalidStateTransition,
    LicenseCancelled,
    LicenseExpired,
    MethodNotAllowed,
    MissingBodyProperty,
    MissingRequestHeader,
    MissingRequestParameter,
    NotAcceptable,
    NotFound,
    NotImplemented,
    ProblemDetails,
    RequestTimeout,
    ServerError,
    ServiceUnavailable,
    Unauthorized,
    UnavailableForLegalReasons,
    UnprocessableContent,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi.requests import Request


_CONTENT_TYPE_HEADER_: str = "Content-Type"

_PROBLEM_JSON_CONTENT_TYPE_: str = "application/problem+json"

ProblemType = (
    AlreadyExists
    | BadRequest
    | BusinessRuleViolation
    | Conflict
    | FailedDependency
    | Forbidden
    | Gone
    | InsufficientStorage
    | InvalidBodyPropertyFormat
    | InvalidBodyPropertyValue
    | InvalidParameters
    | InvalidRequestHeaderFormat
    | InvalidRequestParameterFormat
    | InvalidRequestParameterValue
    | InvalidStateTransition
    | LicenseCancelled
    | LicenseExpired
    | MissingBodyProperty
    | MissingRequestHeader
    | MissingRequestParameter
    | MethodNotAllowed
    | NotAcceptable
    | NotFound
    | NotImplemented
    | RequestTimeout
    | ServerError
    | ServiceUnavailable
    | Unauthorized
    | UnavailableForLegalReasons
    | UnprocessableContent
    | ValidationError
)


def _inline_schema_references(
    value: object,
    definitions: dict[str, object],
    references: frozenset[str] = frozenset(),
) -> object:
    """Inline generated local references so schemas can be embedded in OpenAPI.

    Raises:
        ValueError: If a reference is recursive or is not a local definition.
    """
    if isinstance(value, list):
        return [_inline_schema_references(item, definitions, references) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        reference = value["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise ValueError(f"Unsupported schema reference: {reference!r}")
        if reference in references:
            raise ValueError(f"Recursive schema reference: {reference}")
        definition = definitions[reference.removeprefix("#/$defs/")]
        resolved = _inline_schema_references(definition, definitions, references | {reference})
        if not isinstance(resolved, dict):
            raise TypeError("A schema definition must be an object")
        value = {**resolved, **{key: item for key, item in value.items() if key != "$ref"}}
    return {
        key: _inline_schema_references(item, definitions, references) for key, item in value.items()
    }


def _create_problem_responses() -> dict[int | str, dict[str, object]]:
    """Generate self-contained response schemas grouped by registered HTTP status."""
    schemas_by_status: dict[int, list[object]] = {}
    for model_type in get_args(ProblemType):
        if not isinstance(model_type, type) or not issubclass(model_type, ProblemDetails):
            raise TypeError("ProblemType must contain problem model classes")
        schema = model_type.model_json_schema(mode="serialization")
        definitions = schema.pop("$defs", {})
        resolved = _inline_schema_references(schema, definitions)
        status_code = model_type.model_fields["status"].default
        if not isinstance(status_code, int):
            raise TypeError("A problem model must define an integer status default")
        schemas_by_status.setdefault(status_code, []).append(resolved)
    return {
        status_code: {
            "content": {
                _PROBLEM_JSON_CONTENT_TYPE_: {
                    "schema": schemas[0] if len(schemas) == 1 else {"anyOf": schemas},
                },
            },
        }
        for status_code, schemas in schemas_by_status.items()
    }


# Pass to a FastAPI route decorator with responses=PROBLEM_RESPONSES.
# Inline generated schemas avoid application/json insertion and dangling $defs references.
PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = _create_problem_responses()


class ProblemRegistryException(HTTPException):
    def __init__(
        self,
        *,
        request: Request,
        problem: ProblemType,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        problem.instance = str(request.url.replace(query=""))
        self.status_code = problem.status

        if errors:
            if isinstance(errors, list):
                problem.errors = errors
            else:
                problem.errors = [errors]
        self.detail = problem.model_dump_json(exclude_none=True)

        headers = (headers or {}).copy()
        headers[_CONTENT_TYPE_HEADER_] = _PROBLEM_JSON_CONTENT_TYPE_
        self.headers = headers


class AlreadyExistsException(ProblemRegistryException):
    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(request=request, problem=AlreadyExists(), errors=errors, headers=headers)


class BadRequestException(ProblemRegistryException):
    """Expose the BadRequest problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=BadRequest(), errors=errors, headers=headers)


class BusinessRuleViolationException(ProblemRegistryException):
    """Expose the BusinessRuleViolation problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=BusinessRuleViolation(), errors=errors, headers=headers
        )


class ConflictException(ProblemRegistryException):
    """Expose the Conflict problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=Conflict(), errors=errors, headers=headers)


class FailedDependencyException(ProblemRegistryException):
    """Expose the FailedDependency problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=FailedDependency(), errors=errors, headers=headers
        )


class ForbiddenException(ProblemRegistryException):
    """Expose the Forbidden problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=Forbidden(), errors=errors, headers=headers)


class GoneException(ProblemRegistryException):
    """Expose the Gone problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=Gone(), errors=errors, headers=headers)


class InsufficientStorageException(ProblemRegistryException):
    """Expose the InsufficientStorage problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InsufficientStorage(), errors=errors, headers=headers
        )


class InvalidBodyPropertyFormatException(ProblemRegistryException):
    """Expose the InvalidBodyPropertyFormat problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidBodyPropertyFormat(), errors=errors, headers=headers
        )


class InvalidBodyPropertyValueException(ProblemRegistryException):
    """Expose the InvalidBodyPropertyValue problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidBodyPropertyValue(), errors=errors, headers=headers
        )


class InvalidParametersException(ProblemRegistryException):
    """Expose the InvalidParameters problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidParameters(), errors=errors, headers=headers
        )


class InvalidRequestHeaderFormatException(ProblemRegistryException):
    """Expose the InvalidRequestHeaderFormat problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidRequestHeaderFormat(), errors=errors, headers=headers
        )


class InvalidRequestParameterFormatException(ProblemRegistryException):
    """Expose the InvalidRequestParameterFormat problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidRequestParameterFormat(), errors=errors, headers=headers
        )


class InvalidRequestParameterValueException(ProblemRegistryException):
    """Expose the InvalidRequestParameterValue problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidRequestParameterValue(), errors=errors, headers=headers
        )


class InvalidStateTransitionException(ProblemRegistryException):
    """Expose the InvalidStateTransition problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=InvalidStateTransition(), errors=errors, headers=headers
        )


class LicenseCancelledException(ProblemRegistryException):
    """Expose the LicenseCancelled problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=LicenseCancelled(), errors=errors, headers=headers
        )


class LicenseExpiredException(ProblemRegistryException):
    """Expose the LicenseExpired problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=LicenseExpired(), errors=errors, headers=headers)


class MissingBodyPropertyException(ProblemRegistryException):
    """Expose the MissingBodyProperty problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=MissingBodyProperty(), errors=errors, headers=headers
        )


class MissingRequestHeaderException(ProblemRegistryException):
    """Expose the MissingRequestHeader problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=MissingRequestHeader(), errors=errors, headers=headers
        )


class MissingRequestParameterException(ProblemRegistryException):
    """Expose the MissingRequestParameter problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=MissingRequestParameter(), errors=errors, headers=headers
        )


class MethodNotAllowedException(ProblemRegistryException):
    """Expose the MethodNotAllowed problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=MethodNotAllowed(), errors=errors, headers=headers
        )


class NotAcceptableException(ProblemRegistryException):
    """Expose the NotAcceptable problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=NotAcceptable(), errors=errors, headers=headers)


class NotFoundException(ProblemRegistryException):
    """Expose the NotFound problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=NotFound(), errors=errors, headers=headers)


class NotImplementedException(ProblemRegistryException):
    """Expose the NotImplemented problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=NotImplemented(), errors=errors, headers=headers)


class RequestTimeoutException(ProblemRegistryException):
    """Expose the RequestTimeout problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=RequestTimeout(), errors=errors, headers=headers)


class ServerErrorException(ProblemRegistryException):
    """Expose the ServerError problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=ServerError(), errors=errors, headers=headers)


class ServiceUnavailableException(ProblemRegistryException):
    """Expose the ServiceUnavailable problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=ServiceUnavailable(), errors=errors, headers=headers
        )


class UnauthorizedException(ProblemRegistryException):
    """Expose the Unauthorized problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=Unauthorized(), errors=errors, headers=headers)


class UnavailableForLegalReasonsException(ProblemRegistryException):
    """Expose the UnavailableForLegalReasons problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=UnavailableForLegalReasons(), errors=errors, headers=headers
        )


class UnprocessableContentException(ProblemRegistryException):
    """Expose the UnprocessableContent problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(
            request=request, problem=UnprocessableContent(), errors=errors, headers=headers
        )


class ValidationErrorException(ProblemRegistryException):
    """Expose the ValidationError problem as an HTTP exception."""

    def __init__(
        self,
        request: Request,
        errors: ErrorDetail | list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            instance: URI reference identifying this occurrence, or ``None`` to omit it.
        """
        super().__init__(request=request, problem=ValidationError(), errors=errors, headers=headers)


async def problem_registry_exception_handler(
    request: Request,
    exc: ProblemRegistryException,
) -> Response:
    """Return the serialized problem with its HTTP status and custom headers."""
    return Response(
        status_code=exc.status_code,
        content=exc.detail,
        media_type=_PROBLEM_JSON_CONTENT_TYPE_,
        headers=exc.headers,
    )
