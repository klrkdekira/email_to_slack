all:
	docker build -t klrkdekira/email_to_slack .
	docker push klrkdekira/email_to_slack