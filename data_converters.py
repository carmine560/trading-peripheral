"""Convert between different data structures."""


def dictionary_to_tuple(dictionary):
    """Convert a dictionary to a tuple of key-value pairs."""
    if isinstance(dictionary, dict):
        items = []
        for key, value in sorted(dictionary.items()):
            items.append((key, dictionary_to_tuple(value)))
        return tuple(items)
    return dictionary
