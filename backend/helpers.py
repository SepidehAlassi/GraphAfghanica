def get_value(binding, variable):
    return binding.get(variable, {}).get("value")


def get_language(binding, variable):
    return binding.get(variable, {}).get("xml:lang")

