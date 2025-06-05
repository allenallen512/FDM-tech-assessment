# FDM-tech-assessment

Created a supabase database (postgres) with tables:
- product_group_monthly
- product_groups
- steel_grade_production
- steel_grades

Endpoints:
- /upload/steel_grades
- /upload/product_groups
- /forecast/september

It seemed to be that the "daily_charge_schedule" wasn't really needed or have enough entires to be relevant to predict production to the day and hour granularity. If there were daily production schedules for even just one month, the hour-minute production averages could be calculated and hence planned out. 

Projected heats will round up to the nearest heat.

All files are saved locally as either csv (input files) or json (output for scrapchef)


Potential Flow: 
1. upload "steel_grade_production" this will populate both steel grades and and groups table if they do not already exist
2. upload "product_groups_monthly"
3. call the forecast september endpoint



install dependencies:
<pre>pip install requirements.txt</pre>

to run: <pre>python main_endpoints.py</pre>

to upload the steel grade production excel file:
<pre> 
curl -X POST -F "file=@/Users/allenli/Desktop/Projects/FDM-tech-assessment/data/steel_grade_production.xlsx" \
  http://127.0.0.1:5000/upload/steel_grades</pre>

to upload the product groups monthly excel file:
<pre>
curl -X POST -F "file=@/Users/allenli/Desktop/Projects/FDM-tech-assessment/data/product_groups_monthly.xlsx" \
  http://127.0.0.1:5000/upload/product_groups
</pre>

to get september forecast:
<pre>
curl http://127.0.0.1:5000/forecast/september
</pre>

