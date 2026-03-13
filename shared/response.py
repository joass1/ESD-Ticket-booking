from flask import jsonify, make_response


def success(data, code=200):
    """Return standardized success response."""
    return make_response(jsonify({"code": code, "data": data}), code)


def error(message, code=400):
    """Return standardized error response."""
    return make_response(jsonify({"code": code, "message": message}), code)
