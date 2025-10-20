from api.bank_sandbox import app  # noqa: F401 - re-export for uvicorn

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.bank_sandbox:app", host="0.0.0.0", port=8000, reload=True)


