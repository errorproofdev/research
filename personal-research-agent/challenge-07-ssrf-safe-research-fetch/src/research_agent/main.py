from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from .fetcher import BudgetExceeded, SecureFetcher
from .models import FetchInput, FetchResult
from .policy import FetchBlocked


def create_app(fetcher: SecureFetcher | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Safe Research Fetch")
    app.state.fetcher = fetcher or SecureFetcher()

    @app.post("/research/fetch", response_model=FetchResult)
    def fetch(payload: FetchInput, request: Request):
        try:
            return request.app.state.fetcher.fetch(payload.url, payload.budget, payload.allowed_domains)
        except FetchBlocked as exc:
            raise HTTPException(422, str(exc)) from exc
        except BudgetExceeded as exc:
            raise HTTPException(413, str(exc)) from exc

    return app


app = create_app()
