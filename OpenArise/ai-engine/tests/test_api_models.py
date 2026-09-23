from app.api.models import ErrorCode, ApiError, ErrorResponse, SuccessResponse

def test_api_models():
    err = ApiError(ErrorCode.PROJECT_NOT_FOUND, "Not found")
    assert err.code == ErrorCode.PROJECT_NOT_FOUND
    
    res = ErrorResponse(code=ErrorCode.INTERNAL_ERROR, message="Error")
    assert not res.success
    
    succ = SuccessResponse(data={"key": "value"})
    assert succ.success
    assert succ.data["key"] == "value"
