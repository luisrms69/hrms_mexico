app_name = "hrms_mexico"
app_title = "HRMS México"
app_publisher = "Consultoria en Negocios y Aplicaciones"
app_description = "Cumplimiento laboral mexicano para Frappe HRMS"
app_email = "it@buzola.mx"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext", "hrms"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hrms_mexico",
# 		"logo": "/assets/hrms_mexico/logo.png",
# 		"title": "HRMS México",
# 		"route": "/hrms_mexico",
# 		"has_permission": "hrms_mexico.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `hrms_mexico/dock/hrms_mexico/hrms_mexico.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hrms_mexico/css/hrms_mexico.css"
# app_include_js = "/assets/hrms_mexico/js/hrms_mexico.js"

# include js, css files in header of web template
# web_include_css = "/assets/hrms_mexico/css/hrms_mexico.css"
# web_include_js = "/assets/hrms_mexico/js/hrms_mexico.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hrms_mexico/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hrms_mexico/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hrms_mexico.utils.jinja_methods",
# 	"filters": "hrms_mexico.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hrms_mexico.install.before_install"
# after_install = "hrms_mexico.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hrms_mexico.uninstall.before_uninstall"
# after_uninstall = "hrms_mexico.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hrms_mexico.utils.before_app_install"
# after_app_install = "hrms_mexico.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hrms_mexico.utils.before_app_uninstall"
# after_app_uninstall = "hrms_mexico.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "hrms_mexico.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "hrms_mexico.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hrms_mexico.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["hrms_mexico.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# ADR-0002 — el rol Employee no puede `write`/`delete` marcajes originales (conserva `create`).
has_permission = {
	"Employee Checkin": "hrms_mexico.overrides.employee_checkin.has_permission",
}

# Fixtures versionados — Property Setters de inmutabilidad (set_only_once) del marcaje original.
fixtures = [
	{
		"dt": "Property Setter",
		"filters": [
			[
				"name",
				"in",
				[
					"Employee Checkin-employee-set_only_once",
					"Employee Checkin-time-set_only_once",
					"Employee Checkin-log_type-set_only_once",
				],
			]
		],
	}
]

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# ADR-0002 — inmutabilidad de la evidencia del marcaje original (Employee Checkin).
doc_events = {
	"Employee Checkin": {
		"validate": "hrms_mexico.overrides.employee_checkin.protect_evidence",
		"on_trash": "hrms_mexico.overrides.employee_checkin.block_delete",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"hrms_mexico.tasks.all"
# 	],
# 	"daily": [
# 		"hrms_mexico.tasks.daily"
# 	],
# 	"hourly": [
# 		"hrms_mexico.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hrms_mexico.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hrms_mexico.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hrms_mexico.install.before_tests"

# Bootstrap de tests: crea `_Test Company` + setup (vía setup wizard) si la BD está limpia (p. ej. CI).
before_tests = "hrms_mexico.tests.bootstrap.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "hrms_mexico.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hrms_mexico.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hrms_mexico.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hrms_mexico.utils.before_request"]
# after_request = ["hrms_mexico.utils.after_request"]

# Job Events
# ----------
# before_job = ["hrms_mexico.utils.before_job"]
# after_job = ["hrms_mexico.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hrms_mexico.auth.validate"
# ]

# on_social_login = "hrms_mexico.auth.on_social_login"

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
