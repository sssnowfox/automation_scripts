from datetime import datetime, timedelta

def main():
    try:
        args = demisto.args()
        start_time_str = args.get('starttime')
        end_time_str = args.get('endtime')
        date_format = args.get('date_format', '%Y-%m-%d')

        # Convert strings to date objects
        start_date = datetime.strptime(start_time_str, date_format)
        end_date = datetime.strptime(end_time_str, date_format)

        # Validate that start date is not after end date
        if start_date > end_date:
            return_error("Start time cannot be after end time.")

        date_list = []
        current_date = start_date

        # Append each day in the range
        while current_date <= end_date:
            date_list.append(current_date.strftime(date_format))
            current_date += timedelta(days=1)

        command_result = CommandResults(
            outputs_prefix='DateRangeList',
            outputs_key_field='',
            outputs=date_list,
            readable_output=tableToMarkdown(
                'Generated Date List',
                [{'Date': d} for d in date_list],
                headers=['Date']
            )
        )
        return_results(command_result)

    except Exception as e:
        return_error(f"Failed to generate dates: {str(e)}")

if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
