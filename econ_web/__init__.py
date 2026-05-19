"""Project bootstrap helpers."""

try:
    import pymysql
except ModuleNotFoundError:
    pymysql = None
else:
    # Fake a mysqlclient version so Django can use PyMySQL when it is available.
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.install_as_MySQLdb()
    
