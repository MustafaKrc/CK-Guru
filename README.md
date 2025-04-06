# CK-Guru


## Testing
create test db inside db container with `test_db_name = ${POSTGRES_DB}_test`
`db_username = ${POSTGRES_USER}`

first, exec into db container
run: psql -U `db_username` -D `prod_db_name`
and then run: CREATE DATABASE "`test_db_name`"; #  double quotes for case sensitive naming