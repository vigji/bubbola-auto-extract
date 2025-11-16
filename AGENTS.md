The aim of this project is to evolve a fine-tuned solution for LLM based parsing of documents. It consists of a evaluator component and an extractor component

Use uv for the project - migrate pip projects if you find that legacy.

Make sure that you test exstensively your implementations. Do not submit code that has not run. If there is any blocker to execute the code you are writing hiw it should be executed, make sure you report it and give instructions for testing it.

Do not hallucinate solutions. report blockers. require tokens if necessary.

You have already defined in your env:
a DEEPINFRA_TOKEN
a OPENROUTER_TOKEN
a OPENAI_API_KEY

You can explore models from any of those providers when working on THE EXTRACTOR COMPONENT. make sure you use those only for working for the extraction task. 
You can experiment with invocations but make sure you titrate the number of request never to surpass the oom of a few cents per request. in your final report for each PR make sure you also specify how n of tokens for each model you have use to develop a given solution.


