Project Name: Creating LEAP’s “Earth Well”
Research Thrust Area / Project Lead(s): 
Scientific Machine Learning Research Thrust 
Kara Lamb

Short Project Description:
We will data-mine LEAP’s past research papers and conference proceedings using VLM’s, in order to figure out what data already exists and can be used to evaluate and compare different scientific machine learning methods for parameterization development. We will systematically evaluate and review what ML methods LEAP has used in the past, what data sets, models, and parameterizations we have studied, and where all of those data sets currently live. Time-permitting, we will start setting up a pipeline and testbed for evaluating different scientific machine learning methods on these existing data sets.
Sources:
https://arxiv.org/abs/2412.00568
Proposed Hackathon Tasks:
Use VLMs to summarize all the data sets, methods, and simulations used in all past LEAP research by analyzing the downloaded PDFs from LEAP’s past research papers. In particular, identify what data sets or simulations were used in each study, what field of research/processes were studied, how much data (MBs, GBs, etc.), type of data (time series, spatial, etc.), what model or observations, what ML methods, and where data sets can be accessed
Review methods used and types of problems solved and perform meta-analysis of LEAP’s research over the past 5 years
Identify most promising data sets for the scientific machine learning parameterization development testbed & start pipeline for systematically comparing different methods across various datasets
Identify which data sets would be useful and what are the needs for various downstream tasks for e.g. developing Earth system foundation model
Using LEAP’s past research as a source, start identifying shared pain points or challenges that could be addressed through methodological development in Sci ML. 
Expected Outcomes:
A better understanding of the breadth of LEAP’s existing data sets and ML methods used, that might be used towards Sci ML method development and comparison
A decent start on a test-bed for systematically evaluating different scientific machine learning algorithms across ESM parameterizations in different areas
A data set that includes multi-scale processes (DNS, LES, CRM, etc) & identification of what else might be needed in the future.
Pre-Hack-a-thon Preparation Needed:
List of all past LEAP publications and conference proceedings; PDFs downloaded into an accessible folder; github repo set up for shared development.
Future Directions:
Integrate these dataset with Pangeo (or better document what is already available on Pangeo for this type of testbed comparison)
Create the “Earth Well” (similar to Polymathic AI’s “The Well” data set) that could be used as a benchmark data set for general purpose climate parameterization evaluation, development, and systematic comparison of different methods.
Dependencies, Risks, or Potential Blockers:
A significant amount of data is unavailable except on e.g. Derecho. Data sets are too large to be easily accessed. Mitigation: identify a few simpler benchmark simulations like Lorenz 96 or QG model that can be used in the meantime.
Skills or Expertise Needed:
Would be most useful to mainly have people who are already familiar with data-driven parameterization development or setting up ML pipelines or alternatively, using LLMs and coding agents
