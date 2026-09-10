from pydrive.util.color import color, plain

noun = 'favorite'

print(color.green('green is my', noun))
print(color.green['green is my', noun])

print(plain(color.green('green is my', noun)))
print(plain[color.green.lazy('green is my', noun)])
