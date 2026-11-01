# YottaFlex Insurance Underwriting Platform
## AI Prompt History, Developer Contribution & Responsible LLM Usage

**Submission document**

---

## 1. Purpose of this document

LLM tools were allowed for this assignment. I used AI assistance as a development productivity tool while retaining responsibility for understanding the requirements, making implementation decisions, integrating the components, investigating issues, and reviewing the results.

This document explains:
- where AI accelerated my work;
- where I relied on it more heavily;
- the representative prompts and tasks for which I used it;
- what I personally reviewed, changed, ran, or validated; and
- the distinction between completed work, observed test results, and improvements that remain recommendations.

The prompt history below is representative of the assistance used during development. It is not presented as a verbatim export of every conversation or as an exhaustive record of every prompt.

## 2. My overall contribution

I took primary ownership of the implementation process, from understanding the assignment and organizing the insurance workflow to working across the application modules, database, integration, troubleshooting, and testing.

AI helped me move faster when I needed to:
- understand unfamiliar technical concepts and business workflow details;
- explore implementation approaches;
- draft or refine portions of Python, SQL, API, and frontend code;
- interpret errors and identify possible causes;
- review screenshots and organize observations; and
- structure technical explanations and documentation.

I did not treat AI-generated output as automatically correct. I reviewed suggestions against the assignment requirements, the existing codebase, database constraints, and the behavior I observed when running the application. I adapted suggestions to the project, investigated errors, and distinguished implemented functionality from proposed improvements.

**My approach was: I owned the implementation and engineering decisions; AI accelerated parts of the work; I remained responsible for review, integration, debugging, and validation.**

## 3. Project work and where AI helped

| Work area | Where AI accelerated my work | What I personally handled |
|---|---|---|
| Requirement analysis | Helped break the assignment into actors, entities, modules, and workflow stages. | Interpreted the assignment, prioritized the work, and kept the scope focused on the insurance underwriting use case. |
| Architecture and application structure | Explained possible approaches and the trade-offs between components. | Worked with the selected React, FastAPI, and PostgreSQL structure and made project-level decisions about how the components fit together. |
| Master data generation | Helped draft and refine Python generation logic and explain entity relationships. | Ran the generators, inspected generated datasets, and worked with applicant, insured asset, product, coverage option, risk factor, and product-risk mapping data. |
| Database and data loading | Helped formulate SQL and interpret schema, import, and constraint errors. | Worked with the PostgreSQL schema and data import process, investigated inconsistent or missing values, and preserved existing database records. |
| Risk assessment | Helped explain risk-scoring logic and possible calculation structures. | Worked with the risk-engine implementation, ran its test, and reviewed the resulting score, category, and recommendation. |
| Premium calculation | Helped explain the calculation steps and refine implementation logic. | Ran the premium-engine test and checked the base premium, risk loading, and final premium values. |
| Quote generation | Helped refine code and interpret generation or database errors. | Executed quote generation, examined the output, and investigated data and constraint issues. |
| API and frontend integration | Helped explain API structures, request/response behavior, and integration approaches. | Worked across the React frontend and FastAPI backend and reviewed the behavior of the integrated workflows. |
| Role-based workflows | Helped organize role responsibilities and identify permission boundaries. | Made and reviewed decisions separating customer actions, operational processing, underwriting decisions, and administrative monitoring. |
| Debugging | Helped interpret stack traces, error messages, and screenshots and suggest possible causes. | Ran commands and workflows, examined actual results, and decided which suggested fixes were relevant to the codebase. |
| Testing and review | Helped organize test scenarios and structure screenshot observations. | Executed the tests and manual checks that were performed, reviewed the outputs, and recorded issues requiring further work. |

## 4. Representative AI prompt history

The following prompts summarize the main types of assistance I requested during development. They are representative examples, not a verbatim or exhaustive transcript.

### 4.1 Requirement understanding and planning

**Representative prompts**
- “Break down the insurance underwriting assignment into the main modules and end-to-end workflow.”
- “Identify the actors in this workflow and explain what each role should be allowed to do.”
- “Help me prioritize the implementation while keeping the scope aligned with the assignment.”

**AI accelerated**
- Breaking the assignment into manageable modules.
- Understanding the relationships between applicants, insured assets, products, coverage options, quotes, risk assessment, payments, and policies.
- Organizing the implementation sequence.

**My review and decisions**
- Interpreted the assignment requirements and selected implementation priorities.
- Kept the scope focused on the insurance underwriting workflow.
- Defined the intended separation between Customer, Operations Analyst, Risk Reviewer/Underwriter, and Admin responsibilities.

### 4.2 Master data generation and database

**Representative prompts**
- “Help me generate master data for applicants, insured assets, products, coverage options, and risk factors.”
- “Explain the relationships between these entities and help me check the generated data.”
- “Help me understand this PostgreSQL import error and the check constraint involved.”
- “Why is this required column missing or violating a constraint during CSV import?”

**AI accelerated**
- Drafting and refining Python data-generation logic and SQL.
- Explaining database relationships, required fields, and constraint failures.
- Identifying areas to inspect when imported data did not match the schema.

**My review and validation**
- Ran the data generators and inspected the generated files and record counts.
- Worked with the PostgreSQL schema and import workflow.
- Investigated issues including missing `coverage_premium` values and quote check-constraint failures.
- Preserved the existing database records and Docker volume instead of using a destructive reset as a shortcut.

### 4.3 Risk assessment engine

**Representative prompts**
- “Explain how the risk factors should contribute to a risk score and category.”
- “Help me review the risk-engine implementation and its test output.”
- “What should I verify when the engine returns a risk score and approval recommendation?”

**AI accelerated**
- Explaining the calculation flow and the meaning of the risk score and category.
- Suggesting checks between risk observations, score, category, and recommendation.

**My review and validation**
- Worked with the risk-engine implementation and ran its test.
- Reviewed the recorded test output: risk score **12.0**, risk category **LOW**, decision **APPROVE**.
- Checked the actual output for the test case rather than assuming the generated logic was correct.

### 4.4 Premium calculation engine

**Representative prompts**
- “Explain the premium calculation step by step.”
- “Help me verify the base premium, risk loading, and final premium from this test output.”
- “Check whether the calculation flow is consistent with the configured base rate and risk loading.”

**AI accelerated**
- Explaining the formula and intermediate values.
- Structuring the calculation into understandable steps.

**My review and validation**
- Ran the premium-engine test and reviewed the recorded values:

| Input or result | Test output |
|---|---:|
| Coverage amount | 1,000,000 |
| Base rate | 0.025 |
| Base premium | 25,000.00 |
| Risk score | 40 |
| Risk loading | 1.2000 |
| Final premium | 30,000.00 |

- Checked the relationship between the base premium, risk loading, and final premium for the tested case.

### 4.5 Quote generation and data consistency

**Representative prompts**
- “Help me understand the quote-generator output and the related records created.”
- “Why is the quote import failing with a check-constraint error?”
- “Help me trace the missing coverage premium value through the generation and import process.”

**AI accelerated**
- Explaining the quote-generation flow and interpreting error output.
- Suggesting which generated values and schema constraints to inspect.

**My review and validation**
- Ran the quote generator and inspected its output.
- The recorded generator output reported **4,000 quotes**, **9,296 quote-coverage links**, and **12,000 risk observations**.
- Investigated the mismatch between generated data and database constraints instead of assuming the first suggested fix was correct.

### 4.6 Frontend, backend, and role-based workflows

**Representative prompts**
- “Help me understand how this React screen should communicate with the FastAPI endpoint.”
- “Review this screenshot and identify what is confusing or inconsistent in the workflow.”
- “Separate customer actions from Operations Analyst and underwriting actions.”
- “Which validations must be enforced by the backend rather than only hiding buttons in the frontend?”

**AI accelerated**
- Explaining API integration patterns and request/response behavior.
- Reviewing screenshots and organizing UI observations.
- Identifying permission and validation considerations.

**My review and decisions**
- Worked across the React frontend and FastAPI backend and reviewed application behavior.
- Made workflow decisions separating customer acceptance and payment initiation from Operations Analyst payment verification and policy issuance.
- Kept underwriting review as a distinct human decision rather than treating an automated recommendation as the final approval.
- Recognized that hiding a frontend button is not sufficient authorization; backend role and ownership checks are important.
- Distinguished recommendations from changes that had actually been implemented.

### 4.7 Debugging and troubleshooting

**Representative prompts**
- “Explain this traceback and help me identify the likely root cause.”
- “What does this API or database error mean in the context of this workflow?”
- “Review this screenshot and help me distinguish a frontend issue from a backend or data issue.”

**AI accelerated**
- Translating errors into understandable explanations.
- Suggesting possible causes and investigation steps.
- Helping compare expected and observed behavior.

**My review and decisions**
- Ran the relevant commands and workflows.
- Examined the actual error messages and outputs.
- Evaluated whether suggested fixes applied to the existing code and data.
- Avoided destructive troubleshooting steps that could remove existing database records.

## 5. Recorded technical work and test evidence

The following are concrete activities and outputs recorded during development.

| Area | Recorded work or observed output |
|---|---|
| Master data | Generated datasets for 3,000 applicants and 3,000 insured assets, together with products, coverage options, risk factors, and product-risk mappings. |
| Risk engine | Test output: score 12.0, category LOW, decision APPROVE. |
| Premium engine | Test output: base premium 25,000.00, risk loading 1.2000, final premium 30,000.00 for the tested case. |
| Quote generation | Generator output: 4,000 quotes, 9,296 quote-coverage links, and 12,000 risk observations. |
| Database troubleshooting | Investigated CSV import and PostgreSQL constraint issues, including missing coverage premium values and a quote check-constraint failure. |
| Application review | Reviewed Admin, Customer, and Operations Analyst screens and recorded data-display, usability, and role-permission observations. |

These are recorded outputs from specific development tests. They should not be interpreted as proof that every business scenario, security condition, or production-scale requirement has been fully validated.

## 6. Engineering decisions and judgment

The project required more than generating code. Important implementation and workflow decisions included:

1. **Scope control:** Keeping the solution focused on the assignment's insurance underwriting workflow and treating additional enhancements as recommendations unless implemented.
2. **Role separation:** Distinguishing customer actions, operational processing, underwriting decisions, and administrative monitoring.
3. **Human oversight:** Separating automated risk recommendations from final human underwriting decisions.
4. **Payment scope:** Treating payment as a simulated workflow, not claiming a live payment-gateway integration.
5. **Data safety:** Preserving the existing PostgreSQL database and Docker volume during troubleshooting.
6. **Validation:** Reviewing actual generator outputs, engine test results, application behavior, screenshots, and error messages.

## 7. Responsible use of LLM tools

I used LLM tools in line with the assignment allowance, as an assistant for development and learning—not as a substitute for engineering judgment.

My approach was to:
- provide project-specific context when asking for assistance;
- review generated code, SQL, and explanations before using them;
- adapt suggestions to the existing architecture, schema, and business rules;
- run relevant scripts or workflows and inspect their actual outputs;
- investigate errors rather than assuming an AI suggestion had fixed them;
- avoid presenting unimplemented recommendations as completed features; and
- remain accountable for the final integrated solution and its limitations.

AI assistance was particularly useful when I needed to move quickly through unfamiliar concepts, error messages, boilerplate, and documentation. The project-specific decisions, integration work, investigation, and validation remained my responsibility.



## 8. Closing statement

I took primary ownership of developing and reviewing the YottaFlex insurance underwriting solution. I used AI assistance to accelerate parts of the development process, especially code and SQL drafting, understanding technical concepts, interpreting errors, reviewing screenshots, and organizing documentation.

I remained responsible for deciding how the solution should work, adapting suggestions to the project, integrating the components, investigating issues, running tests, and reviewing the results. I understand that generated code is only useful when it fits the requirements and behaves correctly in the actual application.

**My contribution was not limited to writing code. It included taking responsibility for the engineering workflow: understanding the problem, making decisions, integrating modules, debugging issues, validating outputs, and being transparent about what is complete and what still needs work.**

---

