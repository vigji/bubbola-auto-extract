Use uv and ruff for the python part of the project.

The aim of this project is to evolve a fine-tuned solution for LLM based parsing of documents. It consists of a evaluator component and an extractor component.

When you are tasked with developing / improving a solution, make sure you do not tamper the evaluation by changing the evaluator code. Always ask if you think that there is something wrong with evaluation and it should be fixed, unless i am explicitely asking for changes on the evaluator (or requiring propagations to it, eg, i am asking to update the schema for the parsing. in those cases this is fine).

Make sure that you test exstensively your implementations. Do not submit code that has not run. If there is any blocker to execute the code you are writing hiw it should be executed, make sure you report it and give instructions for testing it.

Do not hallucinate solutions. report blockers. require tokens if necessary.

You have already defined in your env:
a DEEPINFRA_TOKEN
a OPENROUTER_TOKEN
a OPENAI_API_KEY

You can explore models from any of those providers when working on THE EXTRACTOR COMPONENT. make sure you use those only for working for the extraction task. 
You can experiment with invocations but make sure you titrate the number of request never to surpass the oom of a few cents per request. in your final report for each PR make sure you also specify how n of tokens for each model you have use to develop a given solution.


