# Come si dice ...? 
Una pagina per vedere come si distribuisce il dialetto nella provincia di Bergamo.
Si ringrazia https://github.com/guglielmo per il file geojson della provincia di Bergamo.

Made with love by AverageBerghemGuy
Seguici su Instagram https://www.instagram.com/averageberghemguy/

# Cosa fanno i vari file?
  - run.py: file principale, contiene il codice per la creazione della mappa. -> è il file chiamato da github pages per buildare l'ultima mappa a partire dai dati dell'ultimo foglio google sheet inserito
  - run_all.py: file per buildare tutte le mappe a partire dai dati di tutti i fogli google sheet inseriti. Si è reso necessario perché avevo fatto casino e mi serviva ripartire da zero. -> non è chiamato da github pages
  - comesidice.xlsx: file excel con i dati è il file che viene utilizzato da run_all.py -> non è chiamato da github pages
