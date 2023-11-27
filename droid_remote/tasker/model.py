from asyncio import Future
from dataclasses_json import dataclass_json, DataClassJsonMixin, LetterCase
from dataclasses import dataclass


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(frozen=True)
class TaskCallbackData(DataClassJsonMixin):
    correlation_id: str
    return_code: int
    result: str


CallbackFuture = Future[str]
CallbackFutures = dict[str, CallbackFuture]
