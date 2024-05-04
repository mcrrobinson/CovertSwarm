# CovertSwarm

Coding assignment

docker run --name some-postgres -p 5432:5432 -e POSTGRES_PASSWORD=mysecretpassword -d postgres

curl -H 'Authorization: Bearer someauthbearertoken' \
-H 'Content-Type: application/json' \
-d '{"args":"someargs"}' \
-X POST \
http://localhost:8000/job/create

curl -H 'Authorization: Bearer someauthbearertoken' \
-H 'Content-Type: application/json' \
-X GET \
http://localhost:8000/job/status?uuid=51de1bac-c728-4e0a-af3f-75668730b02b

docker run --name some-postgres -p 5432:5432 -e POSTGRES_PASSWORD=mysecretpassword -d postgres
