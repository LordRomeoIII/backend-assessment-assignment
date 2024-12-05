# Backend Assessment Assignment

This repository contains a FastAPI service that connects to a Postgres database. There are two endpoints in this service, the first one serves as an ingestion point for medical claims, and a the second one returns the top providers according to the net fees in the stored claims.

## Base URL

`http://localhost:8000`

## Endpoints

### 1. Claim Processing

This endpoint process a JSON payload that contains a list of multiple entries with the following information:

| Field | Type | Description |
| ----- | ---- | ----------- |
| service_date | string | The date and time of the claim in the format MM/DD/YY HH:MM. |
| submitted_procedure | string | The procedure submitted, must start with D. |
| quadrant | string | Optional value. |
| plan_group_number | string | The plan's group number. |
| subscriber_number | string | The subscriber's number. |
| provider_npi | string | The provider's NPI (10-digit). |
| provider_fees | string | Fees charged by the provider (formatted as $X.XX). |
| allowed_fees | string | Fees allowed by the plan (formatted as $X.XX). |
| member_coinsurance | string | Coinsurance amount paid (formatted as $X.XX). |
| member_copay | string | Copay amount paid (formatted as $X.XX). |

- HTTP Status Codes
  - `200 OK`: Claim successfully processed.
  - `422 Unprocessable Entity`: Validation error in the input data.

### 2. Top Providers

Retrieves the top providers based on the sum of all the claims `net_fee`. It has an optional parameter to define how many providers should return, defaults to `10`.

- HTTP Status Codes
  - `200 OK`: Claim successfully processed.
  - `429 Too Many Requests`: Rate limite exceeded (maiximum 10 requests per minute).

## Environment variables

In the `.env.example` file theres is a sample of the variables that the system expects in order to deploy succesfully.

## How to run

The service can be built and run using the `docker-composer` file in the root of the project.

```Shell
docker-compose up --build app
```

The auto-generated documentation can be accessed at the url: `http://localhost:8000/docs`

## Testing

A suite of tests is included in the `test_main.py` file and uses a temporary transient database defined in the `docker-composer`. In order to run the tests, this auxiliary database must be running which can be achieved by using the command:

```Shell
docker-compose up --build db-test
```

This tests cover most of the functionality of the web service but it is not and exhaustive set of tests.

## Communication between `claim_process` and `payments`

In order to enable the passing of information between these two different services, a good approach would be implementing asynchronous communication via a message queue. This allows to be reliable, easily scalable and resiliento to failures.

The general structure would be as follows:

1. A message broker is initialized.

1. After the regular processing, the claim processing endpoint sends the claim to the payments service using the message broker. Any errors during this step are logged, and we can mark them in the database as "failed to notify payments".

1. A payments service message consumer needs to be implemented as a background task to consume the incomming messages.

1. In this consumer, the messages are parsed and processed. In case of any errors in this step, the message will not be acknowledge so it can try later.

This simple system is able to handle issues of failures and concurrency in the following manner:

### Failures

- If `claim_process` fails to send a message, this can be logged and proceed with the rest of the queue. Retry logic could be implemented or the failed messages could be sent to a "dead queue".

- If `payments` fails to process a received message, the queue could automatically retry according to the configuration. If the amount of retries is too high, it could be sent to a special queue to manually inspect it or reprocessing.

- In the case of a database commit failure, the datanse will rollback and no messages would be dispatched to payments.


### Concurrency

- The message queue system allows the decoupling of the services in the case of multiple `claim_process`, naturally preventing any possible race condition as each concurrent system dispatches their messages independently to the queue.

- For multiple `payments`, theres a bit more of coordination needed. Mainly set up a load balancing strategy in the message broker and make sure that the payments service always generates the same behaviour when handling duplicate message in case of retries.
