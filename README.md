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

---------------------------------------------Solution----------------------------------------

Created a supabase database (postgres) with tables:
- product_group_monthly
- product_groups
- steel_grade_production
- steel_grades

It seemed to be that the "daily_charge_schedule" wasn't really needed or have enough entires to be relevant to predict production to the day and hour granularity. If there were daily production schedules for even just one month, the hour-minute production averages could be calculated and hence planned out. 

Projected heats will round up to the nearest heat.



to run: <pre>python main_endpoints.py</pre>
to test with file stored locally:

<pre>
curl -X POST -F "file=@/Users/allenli/Desktop/Projects/FDM-tech-assessment/data/product_groups_monthly.xlsx" \
  http://127.0.0.1:5000/upload/product_groups
</pre>

to get september forecast:
<pre>
curl http://127.0.0.1:5000/forecast/september
</pre>

Potential Flow: 
1. upload "steel_grade_production" this will populate both steel grades and and groups table if they do not already exist
2. upload "product_groups_monthly"
3. call the 

