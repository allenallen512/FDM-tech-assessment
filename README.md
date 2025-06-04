# FDM-tech-assessment

# Production Planning

Your task is to write a simple API and database schema for a steel plant's production plans.

Depending on the kind of plan the customer wants to produce, steel production is specified either in terms of 
1. a sequence of heats (batches of steel) of specified steel grades to be made each day 
2. a coarse breakdown into different product groups. Each steel grade belongs to a specific 
  product group, but each product group comprises many steel grades. 

However, ScrapChef requires a steel grade breakdown (number of heats of each grade) in order to run.

We have provided some example input files, as well as the number of tons of each steel grade 
made in the last few months (you can assume each heat averages 100t of steel produced).

The API should:
* Accept these files and store them in your database schema (you may change them to a more friendly
  format before uploading)
* Create an endpoint to forecast the September production in a format that ScrapChef can use.

Feel free to ask any clarifying questions at any point.

My work:
to run: python main_endpoints.py

