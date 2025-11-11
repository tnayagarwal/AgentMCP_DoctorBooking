def test_imports():
	import app.main  # noqa: F401
	import app.models  # noqa: F401
	import app.routers.doctors  # noqa: F401
	import app.routers.patients  # noqa: F401
	import app.routers.appointments  # noqa: F401
	import app.routers.admin  # noqa: F401
	import app.routers.nlp  # noqa: F401
	import app.routers.reminders  # noqa: F401


def test_seed_runs():
	from scripts.seed import seed
	seed()
	assert True

