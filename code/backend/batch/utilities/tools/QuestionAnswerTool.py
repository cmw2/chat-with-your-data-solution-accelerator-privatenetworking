import logging
from typing import List
from .AnsweringToolBase import AnsweringToolBase

from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.callbacks import get_openai_callback

from ..helpers.AzureSearchHelper import AzureSearchHelper
from ..helpers.ConfigHelper import ConfigHelper
from ..helpers.LLMHelper import LLMHelper
from ..helpers.EnvHelper import EnvHelper
from ..common.Answer import Answer
from ..common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class QuestionAnswerTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "QuestionAnswer"
        self.vector_store = AzureSearchHelper().get_vector_store()
        self.verbose = True
        self.env_helper = EnvHelper()

    def answer_question(self, question: str, chat_history: List[dict], **kwargs: dict):
        config = ConfigHelper.get_active_config_or_default()
        answering_prompt = PromptTemplate(
            template=config.prompts.answering_prompt,
            input_variables=["question", "sources"],
        )

        llm_helper = LLMHelper()

        # Retrieve documents as sources
        sources = self.vector_store.similarity_search(
            query=question,
            k=int(self.env_helper.AZURE_SEARCH_TOP_K),
            filters=self.env_helper.AZURE_SEARCH_FILTER,
        )

        # Generate answer from sources
        answer_generator = LLMChain(
            llm=llm_helper.get_llm(), prompt=answering_prompt, verbose=self.verbose
        )
        sources_text = "\n\n".join(
            [f"[doc{i+1}]: {source.page_content}" for i, source in enumerate(sources)]
        )

        with get_openai_callback() as cb:
            result = answer_generator({"question": question, "sources": sources_text})

        answer = result["text"]
        logger.debug(f"Answer: {answer}")

        # Generate Answer Object
        source_documents = []
        for source in sources:
            source_document = SourceDocument(
                id=source.metadata["id"],
                content=source.page_content,
                title=source.metadata["title"],
                source=source.metadata["source"],
                chunk=source.metadata["chunk"],
                offset=source.metadata["offset"],
                page_number=source.metadata["page_number"],
                captions=source.metadata["captions"],
                answers=source.metadata["answers"],
            )
            source_documents.append(source_document)

        clean_answer = Answer(
            question=question,
            answer=answer,
            source_documents=source_documents,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
        )
        return clean_answer
