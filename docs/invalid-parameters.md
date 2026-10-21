# Invalid Parameters

This problem occurs when a client request contains invalid or malformed parameters causing the server to reject the request.

Your client application issued a request to an API that contains invalid or malformed parameters.

| Type URI | Title | Recommended HTTP Status Code | Reference |
|----------|-------|------------------------------|-----------|
|https://terradue.github.io/http-apis-problems-detail/invalid-parameters|Invalid Parameters|400||

> **Note** A problem is generally **not** meant to be used for end-user input validation, but for client developer convenience. 


**Example of an `invalid-parameters` problem details:**
```json
{
    "type": "https://terradue.github.io/http-apis-problems-detail/invalid-parameters",
    "title": "Invalid parameters",
    "detail": "The request contained invalid, or malformed parameters (path or header or query)",
    "status": 400,
    "code": "400-02"    
}
```
