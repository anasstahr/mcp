import pytest
import re
from awslabs.aws_api_mcp_server.core.common.errors import CliParsingError, ProhibitedOperatorsError
from awslabs.aws_api_mcp_server.core.parser.lexer import split_cli_command
from awslabs.aws_api_mcp_server.core.parser.parser import parse


@pytest.mark.parametrize(
    'command,expected_tokens',
    [
        ('aws s3 ls', ['aws', 's3', 'ls']),
        (
            'aws cloud9 list-environments --debug',
            ['aws', 'cloud9', 'list-environments', '--debug'],
        ),
        (
            'aws cloud9 list-environments --endpoint http://a.txt',
            ['aws', 'cloud9', 'list-environments', '--endpoint', 'http://a.txt'],
        ),
        # Quoted argument values are a single token, so characters that are
        # rejected as standalone tokens are preserved inside them.
        (
            "aws ec2 describe-instances --query 'Reservations[].Instances[] | [0]'",
            [
                'aws',
                'ec2',
                'describe-instances',
                '--query',
                'Reservations[].Instances[] | [0]',
            ],
        ),
        (
            "aws ec2 describe-images --query 'Images[?CreationDate>=`2024-01-01`].[ImageId]'",
            [
                'aws',
                'ec2',
                'describe-images',
                '--query',
                'Images[?CreationDate>=`2024-01-01`].[ImageId]',
            ],
        ),
        (
            "aws dynamodb scan --table-name a --filter-expression 'n < :v'",
            [
                'aws',
                'dynamodb',
                'scan',
                '--table-name',
                'a',
                '--filter-expression',
                'n < :v',
            ],
        ),
        (
            "aws s3 ls 's3://bucket/weird;key|name'",
            ['aws', 's3', 'ls', 's3://bucket/weird;key|name'],
        ),
        (
            'aws ec2 describe-instances --filters Name=instance-state-name,Values=running',
            [
                'aws',
                'ec2',
                'describe-instances',
                '--filters',
                'Name=instance-state-name,Values=running',
            ],
        ),
    ],
)
def test_split_cli_command_successfully(command, expected_tokens):
    """Test that split_cli_command tokenizes valid CLI commands correctly."""
    tokens = split_cli_command(command)
    assert tokens == expected_tokens


@pytest.mark.parametrize(
    'command',
    [
        "aws ec2 describe-instances --query 'Reservations[].Instances[] | [0]'",
        "aws ec2 describe-images --query 'Images[?CreationDate>=`2024-01-01`].[ImageId]'",
        "aws dynamodb scan --table-name a --filter-expression 'n < :v'",
        'aws ec2 describe-instances --filters Name=instance-state-name,Values=running',
        'aws dynamodb update-item --table-name a --key \'{"id":{"S":"1"}}\' --update-expression \'SET a = :b\'',
    ],
)
def test_quoted_argument_values_still_parse(command):
    """Test that quoted argument values containing operator characters still parse."""
    parse(command)


@pytest.mark.parametrize(
    'command,error,error_args',
    [
        ('aws s3 && rm -rf', ProhibitedOperatorsError, ['&&']),
        ('aws s3 || rm -rf', ProhibitedOperatorsError, ['||']),
        ('aws s3 ls ; cat /etc/passwd', ProhibitedOperatorsError, [';']),
        ('aws s3 ls | cat /etc/passwd', ProhibitedOperatorsError, ['|']),
        ('aws s3 ls & sleep 1', ProhibitedOperatorsError, ['&']),
        ('aws s3 ls > out.txt', ProhibitedOperatorsError, ['>']),
        ('aws s3 ls >> out.txt', ProhibitedOperatorsError, ['>>']),
        ('aws s3 ls 2> out.txt', ProhibitedOperatorsError, ['2>']),
        ('aws s3 ls 2>> out.txt', ProhibitedOperatorsError, ['2>>']),
        ('', CliParsingError, None),
        ('ecs rm', CliParsingError, 'The provided CLI command is not an AWS command'),
        ('aws s3 "', CliParsingError, 'No closing quotation'),
    ],
)
def test_split_cli_command_unsuccessfully(command, error, error_args):
    """Test that split_cli_command raises errors for invalid or prohibited CLI commands."""
    message = None
    if error_args:
        message = re.escape(str(error(error_args)))
    with pytest.raises(error, match=message):
        split_cli_command(command)
