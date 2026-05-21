USE agenda_inteligente;

DELETE FROM recomendaciones WHERE id_usuario = 1;
DELETE FROM recordatorios WHERE id_usuario = 1;
DELETE FROM notas WHERE id_usuario = 1;
DELETE FROM horarios WHERE id_usuario = 1;
DELETE FROM tareas WHERE id_usuario = 1;
DELETE FROM materias WHERE id_usuario = 1;
DELETE FROM usuarios WHERE id_usuario = 1;

INSERT INTO usuarios (id_usuario, nombre, email, contrasena) VALUES (1, 'Estudiante', 'estudiante@correo.com', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92');

INSERT INTO materias (id_usuario, nombre, profesor, color) VALUES
(1, 'Matematicas', 'Carlos Mendez', '#e74c3c'),
(1, 'Programacion', 'Ana Lopez', '#2ecc71'),
(1, 'Base de Datos', 'Pedro Ramirez', '#3498db'),
(1, 'Ingles', 'Sofia Torres', '#f39c12'),
(1, 'Redes', 'Marco Diaz', '#9b59b6');

INSERT INTO tareas (id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado) VALUES
(1, 'Taller de integrales', 'Resolver ejercicios 1-10 del capitulo 5', CURDATE() + INTERVAL 2 DAY, 'alta', 120),
(1, 'Proyecto final POO', 'Avance del proyecto de Java', CURDATE() + INTERVAL 5 DAY, 'alta', 180),
(1, 'Examen de SQL', 'Estudiar joins y subconsultas', CURDATE() + INTERVAL 1 DAY, 'alta', 90),
(1, 'Ensayo de Ingles', 'Escribir 2 paginas sobre tecnologia', CURDATE() + INTERVAL 7 DAY, 'media', 60),
(1, 'Ejercicios de redes', 'Capas OSI y TCP/IP', CURDATE() + INTERVAL 3 DAY, 'media', 45),
(1, 'Lectura base de datos', 'Capitulo 4: Normalizacion', CURDATE() + INTERVAL 10 DAY, 'baja', 30),
(1, 'Taller de matrices', 'Multiplicacion y determinantes', CURDATE() + INTERVAL 4 DAY, 'media', 90),
(1, 'Preparacion exposicion', 'Diapositivas del proyecto', CURDATE() + INTERVAL 6 DAY, 'baja', 60);

INSERT INTO horarios (id_usuario, dia_semana, hora_inicio, hora_fin) VALUES
(1, 'lunes', '08:00', '10:00'),
(1, 'lunes', '14:00', '16:00'),
(1, 'martes', '09:00', '11:00'),
(1, 'martes', '15:00', '17:00'),
(1, 'miercoles', '08:00', '10:00'),
(1, 'miercoles', '14:00', '16:00'),
(1, 'jueves', '10:00', '12:00'),
(1, 'jueves', '15:00', '18:00'),
(1, 'viernes', '08:00', '12:00'),
(1, 'sabado', '09:00', '13:00');

INSERT INTO notas (id_usuario, id_materia, calificacion, descripcion) VALUES
(1, 1, 4.5, 'Parcial 1'),
(1, 2, 3.8, 'Taller'),
(1, 3, 4.2, 'Proyecto modulo 1'),
(1, 4, 4.0, 'Examen parcial'),
(1, 5, 4.8, 'Speaking test');
