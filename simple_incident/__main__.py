import uvicorn


def main() -> None:
    uvicorn.run(
        "simple_incident.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
