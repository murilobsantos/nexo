def media(values):
    return None if not values else sum(values) / len(values)


if __name__ == "__main__":
    print(f"Média: {media([2, 4])}")
